"""Google Calendar integration."""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
from typing import Any, Dict, List

try:  # pragma: no cover - handled in runtime
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except ImportError:  # pragma: no cover - optional dependency
    Credentials = None  # type: ignore
    build = None  # type: ignore

from core.trigger_words import contains_trigger, load_trigger_words


def fetch_events() -> List[Dict[str, Any]]:
    """Fetch upcoming events containing trigger words."""
    words = load_trigger_words()
    if not words:
        return []

    if Credentials is None or build is None:
        raise ImportError("google-api-python-client is required")

    creds_b64 = os.getenv("GOOGLE_CREDENTIALS_JSON_BASE64")
    if creds_b64:
        creds_info = json.loads(base64.b64decode(creds_b64).decode("utf-8"))
    else:
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
        if not all([client_id, client_secret, refresh_token]):
            raise RuntimeError("Google OAuth credentials not configured")
        creds_info = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "token_uri": "https://oauth2.googleapis.com/token",
        }

    creds = Credentials.from_authorized_user_info(creds_info)

    service = build("calendar", "v3", credentials=creds)
    now = dt.datetime.utcnow().isoformat() + "Z"
    events_result = (
        service.events()
        .list(
            calendarId=os.getenv("GOOGLE_CALENDAR_ID", "primary"),
            timeMin=now,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    items = events_result.get("items", [])
    triggered: List[Dict[str, Any]] = []
    for item in items:
        description = item.get("description", "")
        if contains_trigger(description, words):
            triggered.append(
                {
                    "id": item.get("id"),
                    "summary": item.get("summary"),
                    "description": description.strip(),
                    "creator": item.get("creator", {}).get("email"),
                    "start": item.get("start"),
                }
            )
    return triggered


def scheduled_poll() -> List[Dict[str, Any]]:
    """Scheduled poll that returns normalized trigger payloads."""
    events = fetch_events()
    normalized: List[Dict[str, Any]] = []
    for event in events:
        creator = event.get("creator")
        if not creator:
            continue
        normalized.append(
            {
                "creator": creator,
                "trigger_source": "calendar",
                "recipient": creator,
                "payload": event,
            }
        )
    return normalized
