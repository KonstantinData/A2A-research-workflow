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
            personFields="names,emailAddresses,organizations,metadata",
        )
        .execute()
    )
    return result.get("connections", [])
