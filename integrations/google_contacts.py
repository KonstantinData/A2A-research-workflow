"""Google Contacts (People API) integration."""

from __future__ import annotations

import os

from typing import Any, Dict, List, Optional, Callable
from .google_oauth import build_user_credentials, classify_oauth_error

# Google libs optional in Tests
try:  # pragma: no cover
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
except Exception:  # pragma: no cover
    Request = None  # type: ignore
    build = None  # type: ignore

# Scopes required for the People API. ``contacts.other.readonly`` enables
# access to the "Other contacts" bucket which some accounts use for storing
# address book entries. Using both scopes keeps the refresh token compatible
# with either permission set.
SCOPES = [
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/contacts.other.readonly",
]

from core.trigger_words import load_trigger_words
from core import feature_flags, summarize, parser
from core.utils import (
    required_fields,
    optional_fields,
    log_step,
)
from . import email_sender


def _primary_email(person: Dict[str, Any]) -> Optional[str]:
    for item in person.get("emailAddresses", []) or []:
        val = (item or {}).get("value")
        if val:
            return val
    return None


def _notes_blob(person: Dict[str, Any]) -> str:
    notes = person.get("notes") or ""
    for bio in person.get("biographies", []) or []:
        v = (bio or {}).get("value")
        if v:
            notes += ("\n" if notes else "") + v
    for org in person.get("organizations", []) or []:
        n = (org or {}).get("name") or ""
        t = (org or {}).get("title") or ""
        if n or t:
            notes += ("\n" if notes else "") + " ".join(p for p in (n, t) if p)
    for url in person.get("urls", []) or []:
        u = (url or {}).get("value")
        if u:
            notes += ("\n" if notes else "") + u
    return notes


def fetch_contacts(page_size: int = 200, page_limit: int = 10) -> List[Dict[str, Any]]:
    """Live-Fetch (in Tests typischerweise gemonkeypatched)."""
    if build is None or Request is None:  # pragma: no cover
        return []

    try:
        creds = build_user_credentials(SCOPES)
        if not creds:
            log_step(
                "contacts",
                "missing_google_oauth_env",
                {"mode": "v2-only"},
                severity="error",
            )
            return []

        creds.refresh(Request())

        service = build("people", "v1", credentials=creds, cache_discovery=False)
        log_step(
            "contacts",
            "fetch_call",
            {"page_size": page_size, "page_limit": page_limit},
        )

        out: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        pages = 0
        while True:  # pragma: no cover (in CI meist gemonkeypatched)
            resp = (
                service.people()
                .connections()
                .list(
                    resourceName="people/me",
                    pageSize=page_size,
                    pageToken=page_token,
                    personFields="names,emailAddresses,organizations,metadata,biographies,urls,photos",
                    sortOrder="LAST_MODIFIED_DESCENDING",
                    requestSyncToken=False,
                )
                .execute()
            )
            out.extend(resp.get("connections", []) or [])
            page_token = resp.get("nextPageToken")
            pages += 1
            if not page_token or pages >= page_limit:
                break
        return out
    except Exception as e:
        code, hint = classify_oauth_error(e)
        cid_tail = (os.getenv("GOOGLE_CLIENT_ID_V2") or "")[-8:]
        log_step(
            "contacts",
            "fetch_error",
            {"error": str(e), "code": code, "hint": hint, "client_id_tail": cid_tail},
            severity="error",
        )
        return []


# Für orchestrator.gather_triggers wird nur fetch_contacts gebraucht.
# Wenn du später eine Normalisierung brauchst, kannst du hier eine Funktion ergänzen.


def scheduled_poll(fetch_fn: Optional[Callable[[], List[Dict[str, Any]]]] = None) -> List[Dict[str, Any]]:
    """Fetch contacts and normalise them into trigger records.

    The function extracts basic fields from the contact's notes and sends a
    friendly e-mail when required fields are missing. It returns a list of
    dictionaries compatible with the orchestrator's trigger format used in the
    tests.
    """

    if fetch_fn is None:
        fetch_fn = fetch_contacts
    contacts = fetch_fn() or []
    trigger_words = [t.lower() for t in load_trigger_words()]
    triggers: List[Dict[str, Any]] = []
    for person in contacts:
        email = _primary_email(person) or ""
        notes = _notes_blob(person)
        names = [n.get("displayName") for n in person.get("names", []) if n.get("displayName")]
        joined_names = " ".join(names)
        summary_text = f"{notes} {joined_names}".lower()
        matched_trigger = next((t for t in trigger_words if t in summary_text), None)
        contact_id = person.get("resourceName") or person.get("id") or ""
        if matched_trigger:
            log_step(
                "contacts",
                "trigger_detected",
                {"contact_id": contact_id, "name": joined_names, "trigger": matched_trigger},
            )

        company = parser.extract_company(notes) or parser.extract_company(joined_names) or ""
        domain = parser.extract_domain(notes) or parser.extract_domain(joined_names) or ""
        phone = parser.extract_phone(notes) or parser.extract_phone(joined_names) or ""

        payload: Dict[str, Any] = {
            "names": names,
            "company": company,
            "domain": domain,
            "email": email,
            "phone": phone,
            "notes_extracted": {"company": company, "domain": domain, "phone": phone},
        }
        if feature_flags.ENABLE_SUMMARY:
            payload["summary"] = summarize.summarize_notes(notes)

        missing_req = [f for f in required_fields("contacts") if not payload.get(f)]
        missing_opt = [f for f in optional_fields() if not payload.get(f)]
        try:
            if missing_req:
                body = (
                    "Please provide the following information:\n"
                    + "\n".join(f"{f}:" for f in missing_req + missing_opt)
                )
                email_sender.send(
                    to=email or "admin@condata.io",
                    subject="[Research Agent] Missing contact information",
                    body=body,
                )
                log_step(
                    "contacts",
                    "reminder_sent",
                    {"contact_id": contact_id, "missing_fields": missing_req},
                )
        except Exception as e:
            log_step(
                "contacts",
                "reminder_error",
                {"contact_id": contact_id, "error": str(e)},
                severity="critical",
            )

        log_step(
            "contacts",
            "contacts_payload",
            {
                "contact_id": contact_id,
                "name": joined_names,
                "company": company,
                "domain": domain,
                "email": email,
                "phone": phone,
                "missing_required": missing_req,
                "missing_optional": missing_opt,
            },
        )

        triggers.append(
            {
                "creator": email,
                "trigger_source": "contacts",
                "recipient": email,
                "payload": payload,
            }
        )

        log_step(
            "contacts",
            "handoff",
            {"contact_id": contact_id, "agent": "agent1_internal_company_research"},
        )

    return triggers
