#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
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


# Module level defaults are kept for compatibility with tests that patch these
# attributes directly. Runtime helpers still read the live environment so CI
# runs can override values via secrets/variables without relying on the
# constants staying in sync.
_DEFAULT_CAL_IDS = getattr(SETTINGS, "google_calendar_ids", None) or ["primary"]
CAL_IDS = [
    cid
    for cid in (str(x).strip() for x in _DEFAULT_CAL_IDS)
    if cid
]
LOOKBACK_DAYS = SETTINGS.cal_lookback_days
LOOKAHEAD_DAYS = SETTINGS.cal_lookahead_days


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def _parse_calendar_ids(value: str | None) -> List[str]:
    if value is None:
        return []
    raw = value.strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            arr = json.loads(raw)
            ids = [str(x).strip() for x in arr if str(x).strip()]
            return list(dict.fromkeys(ids))
        except Exception:
            pass
    parts = [p.strip() for p in re.split(r"[,\s;]+", raw) if p.strip()]
    return list(dict.fromkeys(parts))


def _calendar_ids() -> List[str]:
    env_ids = _parse_calendar_ids(os.getenv("GOOGLE_CALENDAR_IDS"))
    if env_ids:
        return env_ids
    if CAL_IDS:
        return list(dict.fromkeys(str(x).strip() for x in CAL_IDS if str(x).strip()))
    fallback = getattr(SETTINGS, "google_calendar_ids", None) or ["primary"]
    cleaned = [str(x).strip() for x in fallback if str(x).strip()]
    return list(dict.fromkeys(cleaned)) or ["primary"]


def _time_window() -> tuple[str, str]:
    lookback = _env_int("CAL_LOOKBACK_DAYS", LOOKBACK_DAYS)
    lookahead = _env_int("CAL_LOOKAHEAD_DAYS", LOOKAHEAD_DAYS)
    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    tmin = now - dt.timedelta(days=lookback)
    tmax = now + dt.timedelta(days=lookahead)
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
DOMAIN_REGEX  = r"\b([a-z0-9\-]+\.[a-z]{2,})(/[\S]*)?\b"


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
    cal_ids = _calendar_ids()
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
            for a in ("google_client_id", "google_client_secret", "google_refresh_token")
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
        first_calendar = cal_ids[0] if cal_ids else "primary"
        try:
            service.calendarList().get(calendarId=first_calendar).execute()
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
