#!/usr/bin/env python3
from __future__ import annotations

import os, re
import time
import datetime as dt
from typing import Any, Dict, List

from config.settings import SETTINGS
from core.utils import log_step
from .google_oauth import (
    build_user_credentials,
    classify_oauth_error,
    refresh_access_token,
    OAuthError,
)
from app.core.policy.retry import MAX_ATTEMPTS, backoff_seconds

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except Exception:
    Credentials = None
    build = None

Normalized = Dict[str, Any]

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# --- Test-facing module constants (can be monkeypatched in tests) ---
LOOKAHEAD_DAYS = SETTINGS.cal_lookahead_days
LOOKBACK_DAYS = SETTINGS.cal_lookback_days
CAL_IDS: List[str] = SETTINGS.google_calendar_ids or ["primary"]


def _time_window() -> tuple[str, str]:
    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    tmin = now - dt.timedelta(days=LOOKBACK_DAYS)
    tmax = now + dt.timedelta(days=LOOKAHEAD_DAYS)
    return tmin.isoformat(), tmax.isoformat()


def _normalize(ev: Dict[str, Any], cal_id: str) -> Normalized:
    summary = ev.get("summary") or ""
    description = ev.get("description") or ""
    company = extract_company(summary) or extract_company(description)
    domain = extract_domain(summary) or extract_domain(description)
    return {
        "event_id": ev.get("id"),
        "summary": summary or None,
        "description": description or None,
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
        "organizer": ev.get("organizer"),
        "organizerEmail": (ev.get("organizer") or {}).get("email"),
        "calendarId": cal_id,
        "company_name": company,
        "domain": domain,
    }


COMPANY_REGEX = r"\b([A-Z][A-Za-z0-9&.\- ]{2,}\s(?:GmbH|AG|KG|SE|Ltd|Inc|LLC))\b"
DOMAIN_REGEX = r"\b([a-z0-9\-]+\.[a-z]{2,})(/[\S]*)?\b"


def contains_trigger(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    trigger_words_file = SETTINGS.trigger_words_path or Path("config/trigger_words.txt")
    try:
        with Path(trigger_words_file).open('r', encoding='utf-8') as f:
            trigger_words = [line.strip().lower() for line in f if line.strip()]
        return any(word in text_lower for word in trigger_words)
    except (OSError, IOError):
        # Fallback to hardcoded trigger words if file not found
        fallback_words = ["research", "recherche", "meeting preparation", "besuchsvorbereitung"]
        return any(word in text_lower for word in fallback_words)


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


def fetch_events() -> List[Normalized]:
    results: List[Normalized] = []
    if not build or not Credentials:
        log_step("calendar", "google_api_client_missing", {}, severity="error")
        if SETTINGS.live_mode == 1:
            raise RuntimeError("google_api_client_missing")
        return results
    try:
        creds = build_user_credentials(SCOPES)
        if not creds:
            log_step(
                "calendar",
                "missing_google_oauth_env",
                {"mode": "v2-only"},
                severity="error",
            )
            return []

        if all(
            getattr(SETTINGS, a, None)
            for a in (
                "google_client_id",
                "google_client_secret",
                "google_refresh_token",
            )
        ):
            try:
                creds.token = refresh_access_token()
            except OAuthError:
                log_step(
                    "calendar",
                    "google_invalid_grant",
                    {"message": "Refresh token rejected"},
                    severity="error",
                )
                return []

        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        # Use test-facing CAL_IDS (can be monkeypatched)
        cal_ids: List[str] = CAL_IDS or ["primary"]

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                service.calendarList().get(calendarId=cal_ids[0]).execute()
                break
            except Exception as e:
                if attempt >= MAX_ATTEMPTS:
                    code, hint = classify_oauth_error(e)
                    cid_tail = (SETTINGS.google_client_id or "")[-8:]
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
                delay = backoff_seconds(attempt)
                log_step(
                    "calendar",
                    "calendar_list_retry",
                    {
                        "calendar_id": cal_ids[0],
                        "attempt": attempt,
                        "backoff_seconds": round(delay, 2),
                    },
                    severity="warning",
                )
                time.sleep(delay)

        tmin, tmax = _time_window()
        for cal_id in cal_ids:
            token = None
            while True:
                for attempt in range(1, MAX_ATTEMPTS + 1):
                    try:
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
                        break
                    except Exception as exc:
                        if attempt >= MAX_ATTEMPTS:
                            raise
                        delay = backoff_seconds(attempt)
                        log_step(
                            "calendar",
                            "events_retry",
                            {
                                "calendar_id": cal_id,
                                "attempt": attempt,
                                "backoff_seconds": round(delay, 2),
                                "error": str(exc),
                            },
                            severity="warning",
                        )
                        time.sleep(delay)
                for item in resp.get("items", []):
                    norm = _normalize(item, cal_id)
                    log_step(
                        "calendar",
                        "event_ingested",
                        {"event_id": norm.get("event_id"), "calendar_id": cal_id},
                    )
                    ev = dict(norm)
                    ev["payload"] = dict(norm)
                    results.append(ev)
                token = resp.get("nextPageToken")
                if not token:
                    break

        log_step("calendar", "fetch_ok", {"calendars": cal_ids, "count": len(results)})
    except Exception as e:  # pragma: no cover
        code, hint = classify_oauth_error(e)
        cid_tail = (SETTINGS.google_client_id or "")[-8:]
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
