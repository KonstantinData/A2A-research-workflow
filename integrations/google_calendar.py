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

from core.trigger_words import contains_trigger
from core.translate import to_us_business_english


def fetch_events() -> List[Dict[str, Any]]:
    """Fetch upcoming events containing trigger words."""
    if Credentials is None or build is None:
        raise ImportError("google-api-python-client is required")

    creds_b64 = os.getenv("GOOGLE_CREDENTIALS_JSON_BASE64")
    if not creds_b64:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON_BASE64 not set")

    creds_info = json.loads(base64.b64decode(creds_b64).decode("utf-8"))
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
        if contains_trigger(description):
            translated = to_us_business_english(description.strip())
            triggered.append(
                {
                    "id": item.get("id"),
                    "summary": item.get("summary"),
                    "description": translated,
                    "creator": item.get("creator", {}).get("email"),
                    "start": item.get("start"),
                }
            )
    return triggered
