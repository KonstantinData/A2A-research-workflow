#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from core.utils import log_step

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except Exception:
    Credentials = None
    build = None

Normalized = Dict[str, Any]

# ---------- Hilfsfunktionen für Triggerprüfung etc. ----------
COMPANY_REGEX = r"\b([A-Z][A-Za-z0-9&.\- ]{2,}\s(?:GmbH|AG|KG|SE|Ltd|Inc|LLC))\b"
DOMAIN_REGEX = r"\b([a-z0-9\-]+\.[a-z]{2,})(/[^\s]*)?\b"


def contains_trigger(text: str) -> bool:
    if not text:
        return False
    return "besuchsvorbereitung" in text.lower()


def extract_company(text: str) -> str | None:
    if not text:
        return None
    m = re.search(COMPANY_REGEX, text)
    if m:
        return m.group(1)
    return None


def extract_domain(text: str) -> str | None:
    if not text:
        return None
    m = re.search(DOMAIN_REGEX, text)
    if m:
        return m.group(1).lower()
    return None


# ---------- Hauptfunktion fetch_events ----------
def fetch_events() -> List[Normalized]:
    """Fetch events from Google Calendar API within the configured time window."""

    now = datetime.now(timezone.utc)
    minutes_back = int(os.getenv("CALENDAR_MINUTES_BACK", "1440"))  # 24h
    minutes_fwd = int(os.getenv("CALENDAR_MINUTES_FWD", "10080"))  # 7d
    time_min = (now - timedelta(minutes=minutes_back)).isoformat()
    time_max = (now + timedelta(minutes=minutes_fwd)).isoformat()

    results: List[Dict[str, Any]] = []

    try:
        if not Credentials or not build:
            log_step(
                "calendar",
                "fetch_skipped",
                {"reason": "google libraries not available"},
            )
            return []

        creds = Credentials(
            None,
            refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
            client_id=os.getenv("GOOGLE_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID_V2"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
            or os.getenv("GOOGLE_CLIENT_SECRET_V2"),
            token_uri=os.getenv("GOOGLE_TOKEN_URI"),
        )

        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        items = events_result.get("items", [])
        # 🔍 Neuer Debug-Log: komplette rohe API-Antwort
        log_step("calendar", "raw_api_response", {"response": events_result})

        for ev in items:
            results.append(
                {
                    "event_id": ev.get("id"),
                    "summary": ev.get("summary"),
                    "description": ev.get("description"),
                    "start": ev.get("start"),
                    "end": ev.get("end"),
                    "creatorEmail": (ev.get("creator") or {}).get("email"),
                    "creator": ev.get("creator"),
                }
            )

    except Exception as e:
        log_step("calendar", "fetch_error", {"error": str(e)}, severity="critical")
        return []

    # 📊 Normalisiertes Log mit Übersicht
    log_step(
        "calendar",
        "fetched_events",
        {
            "count": len(results),
            "time_min": time_min,
            "time_max": time_max,
            "ids": [ev.get("event_id") for ev in results],
            "summaries": [ev.get("summary") for ev in results],
            "creator_emails": [ev.get("creatorEmail") for ev in results],
        },
    )

    return results
