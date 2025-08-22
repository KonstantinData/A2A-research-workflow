# integrations/google_contacts.py
"""Google Contacts (People API) integration."""
from __future__ import annotations

import os
from typing import Any, Dict, List

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
except Exception:  # pragma: no cover
    Credentials = None  # type: ignore
    Request = None  # type: ignore
    build = None  # type: ignore

from core.trigger_words import load_trigger_words, contains_trigger


SCOPES = ["https://www.googleapis.com/auth/contacts.readonly"]


def _load_oauth_from_env() -> Dict[str, str]:
    cid = os.getenv("GOOGLE_CLIENT_ID_V2") or os.getenv("GOOGLE_CLIENT_ID")
    csec = os.getenv("GOOGLE_CLIENT_SECRET_V2") or os.getenv("GOOGLE_CLIENT_SECRET")
    rtok = os.getenv("GOOGLE_REFRESH_TOKEN")
    if not (cid and csec and rtok):
        raise RuntimeError("Google OAuth credentials not configured")
    return {"client_id": cid, "client_secret": csec, "refresh_token": rtok}


def _credentials() -> "Credentials":
    cfg = _load_oauth_from_env()
    if Credentials is None:
        raise RuntimeError("google-auth libraries not installed")
    creds = Credentials(
        token=None,
        refresh_token=cfg["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        scopes=SCOPES,
    )
    if Request is None:
        raise RuntimeError("google-auth transport missing")
    creds.refresh(Request())
    return creds


def fetch_contacts(page_size: int = 100) -> List[Dict[str, Any]]:
    """Return recent contacts (connections) using the People API.

    We return a light-weight structure that the orchestrator will normalize.
    """
    words = load_trigger_words()
    if not words:
        return []

    creds = _credentials()
    if build is None:
        return []

    service = build("people", "v1", credentials=creds)
    result = (
        service.people()
        .connections()
        .list(
            resourceName="people/me",
            pageSize=page_size,
            personFields="names,emailAddresses,organizations,metadata,biographies",
        )
        .execute()
    )
    contacts: List[Dict[str, Any]] = result.get("connections", [])

    filtered: List[Dict[str, Any]] = []
    for c in contacts:
        notes = c.get("notes") or ""
        for bio in c.get("biographies", []):
            notes += "\n" + bio.get("value", "")
        names = " ".join(n.get("displayName", "") for n in c.get("names", []))
        content = f"{names}\n{notes}"
        if contains_trigger(content, words):
            filtered.append(c)
    return filtered


def scheduled_poll() -> List[Dict[str, Any]]:
    """Fetch and normalize contact triggers for the orchestrator."""
    contacts = fetch_contacts()
    results: List[Dict[str, Any]] = []
    for c in contacts:
        email = None
        for item in c.get("emailAddresses", []):
            if "value" in item:
                email = item["value"]
                break
        results.append(
            {
                "creator": email,
                "trigger_source": "contacts",
                "recipient": email,
                "payload": c,
            }
        )
    return results
