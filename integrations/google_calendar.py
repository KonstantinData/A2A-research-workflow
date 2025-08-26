from __future__ import annotations

import datetime as dt
import os
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

# optionale OpenAI-Attrappe für Tests (wird gemonkeypatched)
try:
    import openai as _openai  # type: ignore
except Exception:  # keine Lib installiert -> Dummy mit ChatCompletion.create

    class _Dummy:
        class ChatCompletion:
            @staticmethod
            def create(*_a, **_k):
                raise RuntimeError("openai not installed")

    _openai = _Dummy()  # type: ignore

openai = _openai  # Tests patchen google_calendar.openai.ChatCompletion.create

# Zone/Google optional zur Importzeit – Tests nutzen Stubs/Monkeypatch
try:
    from google.oauth2.credentials import Credentials  # pragma: no cover
    from googleapiclient.discovery import build  # pragma: no cover
except Exception:  # pragma: no cover
    Credentials = None  # type: ignore
    build = None  # type: ignore

from core.trigger_words import contains_trigger as _contains_trigger
from core.trigger_words import extract_company as _extract_company

# Exponiere email_sender für Tests (sie patchen google_calendar.email_sender)
from . import email_sender as email_sender  # noqa: F401


# ---------- Hilfsfunktionen, die Tests erwarten ----------
def _utc_now() -> dt.datetime:
    """Separat, damit Tests _utc_now monkeypatchen können."""
    return dt.datetime.now(dt.timezone.utc)


def _dt(s: Dict[str, Any] | None) -> Optional[dt.datetime]:
    if not s:
        return None
    if "dateTime" in s:
        return dt.datetime.fromisoformat(str(s["dateTime"]).replace("Z", "+00:00"))
    if "date" in s:
        return dt.datetime.fromisoformat(str(s["date"]) + "T00:00:00+00:00")
    return None


# ---------- Trigger / Company-Extraction ----------
def contains_trigger(event_or_text: Any, triggers: Optional[List[str]] = None) -> bool:
    """Wrapper für Tests, delegiert an core.trigger_words.contains_trigger."""
    return _contains_trigger(event_or_text, triggers)


def extract_company_ai(title: str, trigger: str) -> str:
    """
    Erst Regex/Regel (extract_company), bei 'Unknown' GPT-Fallback.
    Tests patchen openai.ChatCompletion.create, daher hier auf Modulebene bereitstellen.
    """
    company = _extract_company(title, trigger)
    if company and company != "Unknown":
        return company

    prompt = (
        "Extract the company name from the calendar event title below. "
        "Ignore words like 'Firma', 'Company', 'Client'. "
        'Return only the plain company name, no quotes. If none, return "Unknown".\n\n'
        f'Title: "{title}"'
    )
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        text = resp["choices"][0]["message"]["content"].strip()
        return text or "Unknown"
    except Exception:
        return "Unknown"


# ---------- Event Normalisierung & Fetch ----------
def normalize_event(
    ev: Dict[str, Any],
    detected_trigger: Optional[str] = None,
    creator_email: Optional[str] = None,
    creator_name: Optional[str] = None,
) -> Dict[str, Any]:
    title = ev.get("summary") or "Untitled"
    start_dt = _dt(ev.get("start"))
    end_dt = _dt(ev.get("end"))
    tz = (ev.get("start") or {}).get("timeZone") or ev.get("timeZone")

    company = extract_company_ai(title, detected_trigger or "")

    return {
        "event_id": ev.get("id"),  # tolerant: Tests liefern evtl. kein id
        "ical_uid": ev.get("iCalUID"),
        "title": title,
        "company": company,
        "start_iso": start_dt.isoformat() if start_dt else None,
        "end_iso": end_dt.isoformat() if end_dt else None,
        "timezone": tz,
        "creator": creator_email,
        "creator_name": creator_name,
    }


def _oauth_credentials() -> "Credentials":  # pragma: no cover (echter Lauf)
    if Credentials is None:
        raise RuntimeError("google-auth not installed")
    cfg = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "refresh_token": os.getenv("GOOGLE_REFRESH_TOKEN"),
    }
    missing = [k for k, v in cfg.items() if not v]
    if missing:
        raise RuntimeError("Missing Google OAuth env: " + ", ".join(missing))
    return Credentials(
        token=None,
        refresh_token=cfg["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    )


def fetch_events() -> List[Dict[str, Any]]:
    """
    Echtes Fetch nur im Livebetrieb; in Tests wird diese Funktion gemonkeypatched.
    """
    if build is None:
        return []  # in Tests okay
    service = build(
        "calendar", "v3", credentials=_oauth_credentials(), cache_discovery=False
    )
    now = _utc_now()
    time_min = (now - dt.timedelta(days=7)).isoformat().replace("+00:00", "Z")
    time_max = (now + dt.timedelta(days=60)).isoformat().replace("+00:00", "Z")
    resp = (
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
    return resp.get("items", [])
