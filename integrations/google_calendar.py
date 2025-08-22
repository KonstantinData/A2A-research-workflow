# integrations/google_calendar.py
"""Google Calendar integration."""
from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List, Iterable, Optional

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
except Exception:  # pragma: no cover - optional in tests
    Credentials = None  # type: ignore
    Request = None  # type: ignore
    build = None  # type: ignore

from core.trigger_words import contains_trigger, load_trigger_words


SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _load_oauth_from_env() -> Dict[str, str]:
    """Read OAuth credentials from env (supports *V2 fallback*)."""
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
    # Refresh to obtain access token
    if Request is None:
        raise RuntimeError("google-auth Request transport missing")
    creds.refresh(Request())
    return creds


def fetch_events(
    minutes_back: int = 30, minutes_forward: int = 120
) -> List[Dict[str, Any]]:
    """Return recent events from the primary calendar filtered by trigger words.

    We fetch a time window around 'now' and then filter using trigger words.
    """
    creds = _credentials()
    if build is None:
        return []  # graceful degradation for environments without google libs

    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    time_min = (now - dt.timedelta(minutes=minutes_back)).isoformat()
    time_max = (now + dt.timedelta(minutes=minutes_forward)).isoformat()

    service = build("calendar", "v3", credentials=creds)
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=50,
        )
        .execute()
    )
    events: List[Dict[str, Any]] = events_result.get("items", [])

    words = load_trigger_words()
    filtered: List[Dict[str, Any]] = []
    for ev in events:
        summary = ev.get("summary") or ""
        description = ev.get("description") or ""
        content = f"{summary}\n{description}"
        if not words or contains_trigger(content, words):
            filtered.append(ev)
    return filtered
