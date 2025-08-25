# integrations/google_calendar.py
"""Google Calendar integration (LIVE, strict env, no silent fallbacks)."""
from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List, Optional

# Google client libs are optional at import time (tests),
# but REQUIRED at runtime; we fail hard in _credentials/_service if missing.
try:  # pragma: no cover - import guard for environments without google libs
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except Exception:  # pragma: no cover
    Credentials = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]
    build = None  # type: ignore[assignment]
    HttpError = Exception  # type: ignore[assignment]

from core.trigger_words import contains_trigger, load_trigger_words

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _load_oauth_from_env() -> Dict[str, str]:
    """
    Load OAuth creds strictly from environment variables (set by GitHub Actions
    secrets/variables). Fails hard if anything is missing.

    Required:
      - GOOGLE_CLIENT_ID
      - GOOGLE_CLIENT_SECRET
      - GOOGLE_REFRESH_TOKEN
    """
    required = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            "Google OAuth credentials not configured. Missing: " + ", ".join(missing)
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
    # obtain an access token
    creds.refresh(Request())
    return creds


def _service():
    if build is None:
        raise RuntimeError("google-api-python-client is not installed")
    return build("calendar", "v3", credentials=_credentials(), cache_discovery=False)


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def fetch_events(
    minutes_back: int = 30,
    minutes_forward: int = 120,
    calendar_id: str = "primary",
    max_results_per_page: int = 250,
) -> List[Dict[str, Any]]:
    """
    Return recent events from the given calendar filtered by trigger words.

    - Fails hard if trigger words are not configured or Google libs are missing.
    - Paginates through all results within the time window.
    """
    words = load_trigger_words()
    if not words:
        raise RuntimeError(
            "Google Calendar: no trigger words configured (core.trigger_words)"
        )

    now = _utc_now()
    time_min = (now - dt.timedelta(minutes=minutes_back)).isoformat()
    time_max = (now + dt.timedelta(minutes=minutes_forward)).isoformat()

    service = _service()

    filtered: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    try:
        while True:
            req = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=max_results_per_page,
                pageToken=page_token,
            )
            resp = req.execute()
            items: List[Dict[str, Any]] = resp.get("items", [])  # type: ignore[assignment]
            for ev in items:
                summary = ev.get("summary") or ""
                description = ev.get("description") or ""
                content = f"{summary}\n{description}"
                if contains_trigger(content, words):
                    filtered.append(ev)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    except HttpError as e:
        # Surface live errors clearly – no silent degradation
        raise RuntimeError(f"Google Calendar API error: {e}") from e

    return filtered


def scheduled_poll() -> List[Dict[str, Any]]:
    """
    Fetch and normalize calendar events for the orchestrator.

    Output shape per event:
      {
        "creator": "<email>",
        "trigger_source": "calendar",
        "recipient": "<email>",
        "payload": <raw google event dict>
      }
    """
    events = fetch_events()
    results: List[Dict[str, Any]] = []
    for ev in events:
        creator_info = ev.get("creator")
        organizer = ev.get("organizer") or {}
        creator_email = (
            (
                creator_info.get("email")
                if isinstance(creator_info, dict)
                else creator_info
            )
            or organizer.get("email")
            or ""
        )
        results.append(
            {
                "creator": creator_email,
                "trigger_source": "calendar",
                "recipient": creator_email,
                "payload": ev,
            }
        )
    return results
