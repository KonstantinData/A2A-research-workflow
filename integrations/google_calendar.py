#!/usr/bin/env python3
from __future__ import annotations

import os, re
import datetime as dt
from typing import Any, Dict, List

from core.utils import log_step
from .google_oauth import build_user_credentials, classify_oauth_error

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except Exception:
    Credentials = None
    build = None

Normalized = Dict[str, Any]

LOOKAHEAD_DAYS = int(os.getenv("CAL_LOOKAHEAD_DAYS", "14"))
LOOKBACK_DAYS = int(os.getenv("CAL_LOOKBACK_DAYS", "1"))
CAL_IDS = [c.strip() for c in os.getenv("GOOGLE_CALENDAR_IDS", "primary").split(",") if c.strip()]
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _time_window() -> tuple[str, str]:
    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    tmin = now - dt.timedelta(days=LOOKBACK_DAYS)
    tmax = now + dt.timedelta(days=LOOKAHEAD_DAYS)
    return tmin.isoformat(), tmax.isoformat()


def _normalize(ev: Dict[str, Any], cal_id: str) -> Normalized:
    return {
        "event_id": ev.get("id"),
        "summary": ev.get("summary"),
        "description": ev.get("description"),
        "location": ev.get("location"),
        "attendees": [
            {"email": a.get("email")}
            for a in ev.get("attendees", []) or []
            if isinstance(a, dict)
        ],
        "start": ev.get("start"),
        "end": ev.get("end"),
        "creatorEmail": (ev.get("creator") or {}).get("email"),
        "creator": ev.get("creator"),
        "calendarId": cal_id,
    }


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
    results: List[Normalized] = []
    try:
        if build:
            creds = build_user_credentials(SCOPES)
            if not creds:
                log_step(
                    "calendar",
                    "missing_google_oauth_env",
                    {"mode": "v2-only"},
                    severity="error",
                )
                return []
            service = build("calendar", "v3", credentials=creds, cache_discovery=False)
            try:
                service.calendarList().get(calendarId=CAL_IDS[0]).execute()
            except Exception as e:
                code, hint = classify_oauth_error(e)
                cid_tail = (os.getenv("GOOGLE_CLIENT_ID_V2") or "")[-8:]
                log_step(
                    "calendar",
                    "fetch_error",
                    {
                        "error": str(e),
                        "code": code,
                        "hint": hint,
                        "client_id_tail": cid_tail,
                    },
                    severity="error",
                )
                return []
            tmin, tmax = _time_window()
            for cal_id in CAL_IDS:
                token = None
                while True:
                    resp = (
                        service.events()
                        .list(
                            calendarId=cal_id,
                            timeMin=tmin,
                            timeMax=tmax,
                            singleEvents=True,
                            orderBy="startTime",
                            maxResults=2500,
                            pageToken=token,
                        )
                        .execute()
                    )
                    for item in resp.get("items", []):
                        results.append(_normalize(item, cal_id))
                    token = resp.get("nextPageToken")
                    if not token:
                        break
            log_step("calendar", "fetch_ok", {"calendars": CAL_IDS, "count": len(results)})
    except Exception as e:  # pragma: no cover
        code, hint = classify_oauth_error(e)
        cid_tail = (os.getenv("GOOGLE_CLIENT_ID_V2") or "")[-8:]
        log_step(
            "calendar",
            "fetch_error",
            {
                "error": str(e),
                "code": code,
                "hint": hint,
                "client_id_tail": cid_tail,
            },
            severity="error",
        )
    return results
