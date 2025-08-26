"""Google Contacts (People API) integration."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Google libs optional in Tests
try:  # pragma: no cover
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
except Exception:  # pragma: no cover
    Credentials = None  # type: ignore
    Request = None  # type: ignore
    build = None  # type: ignore

from core.trigger_words import load_trigger_words
from core import feature_flags, summarize, parser
from core.utils import normalize_text, already_processed, mark_processed
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
    if build is None or Credentials is None or Request is None:  # pragma: no cover
        return []

    required = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:  # pragma: no cover
        raise RuntimeError("Missing Google OAuth env: " + ", ".join(missing))

    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/contacts.readonly"],
    )
    creds.refresh(Request())
    service = build("people", "v1", credentials=creds, cache_discovery=False)

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


# Für orchestrator.gather_triggers wird nur fetch_contacts gebraucht.
# Wenn du später eine Normalisierung brauchst, kannst du hier eine Funktion ergänzen.
