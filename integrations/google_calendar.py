from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

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

from core.trigger_words import (
    contains_trigger as _contains_trigger,
    extract_company as _extract_company,
    load_trigger_words as _load_trigger_words,
)
from core.utils import (
    required_fields,
    optional_fields,
    already_processed,
    mark_processed,
    log_step,
)
from core import parser

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


def load_trigger_words() -> List[str]:
    """Expose ``core.trigger_words.load_trigger_words`` for tests."""
    return _load_trigger_words()


def extract_company(title: str, trigger: str) -> str:
    """Expose the rule based company extractor for monkeypatching."""
    return _extract_company(title, trigger)


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


def _calendar_ids(cid: str | None = None) -> List[str]:  # pragma: no cover - simple helper
    """Return calendar IDs to poll.``cid`` parameter kept for tests."""
    return [cid or "primary"]


def _service():  # pragma: no cover - real service only in live environment
    if build is None:
        raise RuntimeError("googleapiclient not installed")
    return build("calendar", "v3", credentials=_oauth_credentials(), cache_discovery=False)


def fetch_events() -> List[Dict[str, Any]]:
    """Fetch upcoming calendar events and filter by trigger words."""

    service = _service()
    now = _utc_now()
    minutes_back = int(os.getenv("CALENDAR_MINUTES_BACK", str(7 * 24 * 60)))
    minutes_fwd = int(os.getenv("CALENDAR_MINUTES_FWD", str(60 * 24 * 60)))
    time_min = (now - dt.timedelta(minutes=minutes_back)).isoformat().replace("+00:00", "Z")
    time_max = (now + dt.timedelta(minutes=minutes_fwd)).isoformat().replace("+00:00", "Z")

    items: List[Dict[str, Any]] = []
    for cal_id in _calendar_ids(None):
        resp = (
            service.events()
            .list(
                calendarId=cal_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        items.extend(resp.get("items", []))

    triggers = [t.lower() for t in load_trigger_words()]
    logfile = Path("logs/processed_events.jsonl")
    results: List[Dict[str, Any]] = []
    for ev in items:
        summary = (ev.get("summary") or "").lower()
        matched_trigger = next((t for t in triggers if t in summary), None)
        if not matched_trigger:
            continue
        ev_id = ev.get("id") or ""
        log_step(
            "calendar",
            "trigger_detected",
            {"event_id": ev_id, "title": ev.get("summary"), "trigger": matched_trigger},
        )
        updated = ev.get("updated") or ""
        if already_processed(ev_id, updated, logfile):
            log_step(
                "calendar",
                "skipped",
                {"event_id": ev_id, "title": ev.get("summary"), "updated": updated},
            )
            continue

        mark_processed(ev_id, updated, logfile)

        log_step(
            "calendar",
            "new_event",
            {
                "event_id": ev_id,
                "title": ev.get("summary"),
                "start": ev.get("start"),
                "end": ev.get("end"),
                "updated": updated,
            },
        )

        results.append(ev)
    return results


def scheduled_poll(fetch_fn: Optional[Callable[[], List[Dict[str, Any]]]] = None) -> List[Dict[str, Any]]:
    """Fetch calendar events, normalise them and request missing info."""

    if fetch_fn is None:
        fetch_fn = fetch_events
    events = fetch_fn() or []
    triggers: List[Dict[str, Any]] = []
    for ev in events:
        creator = (ev.get("creator") or {}).get("email") or ev.get("creatorEmail") or ""
        description = ev.get("description") or ""
        title = ev.get("summary") or ""
        # Try to extract company/domain/phone from the description first.  If
        # nothing is found fall back to the event title.  The title often
        # contains both the trigger word and the company name on the same line.
        # Using parser.extract_* on the title helps capture these cases.
        company = parser.extract_company(description) or parser.extract_company(title) or ""
        domain = parser.extract_domain(description) or parser.extract_domain(title) or ""
        phone = parser.extract_phone(description) or parser.extract_phone(title) or ""
        notes = {"company": company, "domain": domain, "phone": phone}

        start_dt = _dt(ev.get("start"))
        end_dt = _dt(ev.get("end"))
        payload: Dict[str, Any] = {
            "title": ev.get("summary"),
            "description": description,
            "company": company,
            "domain": domain,
            "email": creator,
            "phone": phone,
            "notes_extracted": notes,
            "event_id": ev.get("id"),
            "start_iso": start_dt.isoformat() if start_dt else None,
            "end_iso": end_dt.isoformat() if end_dt else None,
        }

        missing_req = [f for f in required_fields("calendar") if not payload.get(f)]
        missing_opt = [f for f in optional_fields() if not payload.get(f)]
        try:
            if missing_req:
                email_sender.send_reminder(
                    to=creator,
                    creator_email=creator,
                    creator_name=None,
                    event_id=payload["event_id"],
                    event_title=payload.get("title", ""),
                    event_start=start_dt,
                    event_end=end_dt,
                    missing_fields=missing_req,
                )
                log_step(
                    "calendar",
                    "reminder_sent",
                    {"event_id": payload.get("event_id"), "missing_fields": missing_req},
                )
        except Exception as e:
            log_step(
                "calendar",
                "reminder_error",
                {"event_id": payload.get("event_id"), "error": str(e)},
            )

        log_step(
            "calendar",
            "scheduled_poll_event",
            {
                "event_id": payload.get("event_id"),
                "title": payload.get("title"),
                "company": payload.get("company"),
                "domain": payload.get("domain"),
                "email": payload.get("email"),
                "phone": payload.get("phone"),
                "missing_required": missing_req,
                "missing_optional": missing_opt,
            },
        )

        triggers.append(
            {
                "creator": creator,
                "trigger_source": "calendar",
                "recipient": creator,
                "payload": payload,
            }
        )

        log_step(
            "calendar",
            "handoff",
            {"event_id": payload.get("event_id"), "agent": "agent1_internal_company_research"},
        )

    return triggers
