# integrations/google_contacts.py
"""Google Contacts (People API) integration (LIVE, strict env, no silent fallbacks)."""
from __future__ import annotations

import datetime as dt
import importlib.util as _ilu
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - import guard
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except Exception:  # pragma: no cover
    Credentials = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]
    build = None  # type: ignore[assignment]
    HttpError = Exception  # type: ignore[assignment]

from core.trigger_words import load_trigger_words
from core import feature_flags, summarize, parser
from core.utils import normalize_text, already_processed, mark_processed
from . import email_sender


def contains_trigger(text: str, trigger_words: list[str]) -> bool:
    text = normalize_text(text)
    return any(normalize_text(t) in text for t in trigger_words)


_JSONL_PATH = Path(__file__).resolve().parents[1] / "logging" / "jsonl_sink.py"
_spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]
append_jsonl = _mod.append

_LOG_PATH = Path("logs") / "workflows" / "contacts.jsonl"
_PROCESSED_PATH = Path("logs") / "processed_contacts.jsonl"


def _load_required_fields(source: str) -> List[str]:
    path = Path(__file__).resolve().parents[1] / "config" / "required_fields.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get(source, [])


SCOPES = ["https://www.googleapis.com/auth/contacts.readonly"]


def _load_oauth_from_env() -> Dict[str, str]:
    required = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            "Google Contacts: OAuth credentials not configured. Missing: "
            + ", ".join(missing)
        )
    return {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_REFRESH_TOKEN"],
    }


def _credentials() -> "Credentials":
    if Credentials is None or Request is None:
        raise RuntimeError("google-auth libraries are not installed")
    cfg = _load_oauth_from_env()
    creds = Credentials(
        token=None,
        refresh_token=cfg["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def _service():
    if build is None:
        raise RuntimeError("google-api-python-client is not installed")
    return build("people", "v1", credentials=_credentials(), cache_discovery=False)


def _primary_email(person: Dict[str, Any]) -> Optional[str]:
    for item in person.get("emailAddresses", []) or []:
        val = item.get("value")
        if val:
            return val
    return None


def _notes_blob(person: Dict[str, Any]) -> str:
    notes = person.get("notes") or ""
    for bio in person.get("biographies", []) or []:
        notes += ("\n" if notes else "") + (bio.get("value") or "")
    for org in person.get("organizations", []) or []:
        name = org.get("name") or ""
        title = org.get("title") or ""
        if name or title:
            notes += ("\n" if notes else "") + " ".join(p for p in (name, title) if p)
    for url in person.get("urls", []) or []:
        u = url.get("value")
        if u:
            notes += ("\n" if notes else "") + u
    return notes


def fetch_contacts(page_size: int = 200, page_limit: int = 10) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    try:
        words = load_trigger_words()
        if not words:
            raise RuntimeError("Google Contacts: no trigger words configured")

        service = _service()

        page_token: Optional[str] = None
        pages = 0
        while True:
            req = (
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
            )
            resp = req.execute()
            people: List[Dict[str, Any]] = resp.get("connections", [])
            for p in people:
                uid = p.get("resourceName")
                updated = ((p.get("metadata") or {}).get("sources") or [{}])[0].get(
                    "updateTime"
                )
                if not uid or not updated:
                    continue
                if already_processed(uid, updated, _PROCESSED_PATH):
                    append_jsonl(_LOG_PATH, {"status": "skipped", "id": uid})
                    continue
                names = " ".join(
                    (n.get("displayName") or "") for n in (p.get("names") or [])
                )
                blob = f"{names}\n{_notes_blob(p)}".strip()
                if contains_trigger(blob, words):
                    person = dict(p)
                    if feature_flags.ENABLE_SUMMARY:
                        person["summary"] = summarize.summarize_notes(blob or names)
                    notes = {
                        "company": parser.extract_company(blob),
                        "domain": parser.extract_domain(blob),
                        "phone": parser.extract_phone(blob),
                    }
                    person["notes_extracted"] = notes
                    filtered.append(person)
                    mark_processed(uid, updated, _PROCESSED_PATH)
                    append_jsonl(_LOG_PATH, {"status": "hit", "payload": person})
            page_token = resp.get("nextPageToken")
            pages += 1
            if not page_token or pages >= page_limit:
                break
    except Exception as e:
        append_jsonl(_LOG_PATH, {"status": "error", "error": str(e)})
        raise RuntimeError(f"Google Contacts API error: {e}") from e

    return filtered


def scheduled_poll() -> List[Dict[str, Any]]:
    contacts = fetch_contacts()
    required = _load_required_fields("contacts")
    results: List[Dict[str, Any]] = []
    for c in contacts:
        if feature_flags.ENABLE_SUMMARY and "summary" not in c:
            c = dict(c)
            names = " ".join(
                (n.get("displayName") or "") for n in (c.get("names") or [])
            )
            c["summary"] = summarize.summarize_notes(_notes_blob(c) or names)

        email = _primary_email(c) or ""
        notes_blob = _notes_blob(c)
        notes = c.get("notes_extracted") or {
            "company": parser.extract_company(notes_blob),
            "domain": parser.extract_domain(notes_blob),
            "phone": parser.extract_phone(notes_blob),
        }
        payload: Dict[str, Any] = {
            "names": [
                n.get("displayName") for n in c.get("names", []) if n.get("displayName")
            ],
            "company": notes.get("company"),
            "domain": notes.get("domain"),
            "email": email,
            "phone": notes.get("phone"),
            "notes_extracted": notes,
        }
        if "summary" in c:
            payload["summary"] = c["summary"]

        missing = [f for f in required if not payload.get(f)]
        if missing:
            body = "Please provide the following missing fields: " + ", ".join(missing)
            email_sender.send_email(
                to=email, subject="Information missing for contact entry", body=body
            )

        results.append(
            {
                "creator": email,
                "trigger_source": "contacts",
                "recipient": email,
                "payload": payload,
            }
        )
    return results
