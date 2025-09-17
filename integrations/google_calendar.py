#!/usr/bin/env python3
from __future__ import annotations

import os, re
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

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except Exception:
    Credentials = None
    build = None

Normalized = Dict[str, Any]

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _time_window() -> tuple[str, str]:
    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    # Laufzeitwerte direkt aus SETTINGS (kein Import-Caching)
    tmin = now - dt.timedelta(days=SETTINGS.cal_lookback_days)
    tmax = now + dt.timedelta(days=SETTINGS.cal_lookahead_days)
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
        "calendarId": cal_id,
        "company_name": company,
        "domain": domain,
    }


COMPANY_REGEX = r"\b([A-Z][A-Za-z0-9&.\- ]{2,}\s(?:GmbH|AG|KG|SE|Ltd|Inc|LLC))\b"
DOMAIN_REGEX = r"\b([a-z0-9\-]+\.[a-z]{2,})(/[\S]*)?\b"


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


def fetch_events() -> List[Normalized]:
    results: List[Normalized] = []
    if not build or not Credentials:
        log_step("calendar", "google_api_client_missing", {}, severity="error")
        if os.getenv("LIVE_MODE", "1") == "1":
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

        # Kalender-IDs erst zur Laufzeit aus SETTINGS lesen
        cal_ids: List[str] = SETTINGS.google_calendar_ids or ["primary"]

        try:
            service.calendarList().get(calendarId=cal_ids[0]).execute()
        except Exception as e:
            code, hint = classify_oauth_error(e)
            cid_tail = (os.getenv("GOOGLE_CLIENT_ID") or "")[-8:]
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
        for cal_id in cal_ids:
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
        cid_tail = (os.getenv("GOOGLE_CLIENT_ID") or "")[-8:]
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
