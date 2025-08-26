# integrations/google_calendar.py
"""Google Calendar integration (LIVE, strict env, no silent fallbacks)."""
from __future__ import annotations

import datetime as dt
import importlib.util as _ilu
import json
import os
import re
try:  # pragma: no cover - optional dependency
    import openai  # type: ignore
except Exception:  # pragma: no cover
    class _DummyChatCompletion:
        @staticmethod
        def create(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("openai package not installed")

    class _DummyOpenAI:
        ChatCompletion = _DummyChatCompletion
        api_key: Optional[str] = None

    openai = _DummyOpenAI()  # type: ignore[assignment]
from pathlib import Path
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

from core.trigger_words import load_trigger_words
from core.utils import normalize_text, already_processed, mark_processed, optional_fields
from core import parser
from . import email_sender

if getattr(openai, "api_key", None) is not None:
    openai.api_key = os.getenv("OPENAI_API_KEY")


def contains_trigger(event: dict, trigger_words: list[str]) -> str | None:
    title = normalize_text(event.get("summary", ""))
    desc = normalize_text(event.get("description", ""))
    for t in trigger_words:
        t_norm = normalize_text(t)
        if t_norm in title or t_norm in desc:
            return t
    return None


def extract_company(title: str, trigger: str) -> Optional[str]:
    """Extract company name from ``title`` following the ``trigger``."""
    if not title or not trigger:
        return None
    idx = title.lower().find(trigger.lower())
    if idx == -1:
        return None
    remainder = title[idx + len(trigger) :].lstrip(" :\-–—")
    remainder = re.sub(r"^(Firma|Company)\s+", "", remainder, flags=re.IGNORECASE)
    company = remainder.strip()
    return company or None


def extract_company_ai(title: str, trigger: str) -> str:
    """
    Hybrid extraction for company names:
    1. Try regex-based extraction.
    2. If it fails or returns 'Unknown', fallback to OpenAI GPT.
    """
    company = extract_company(title, trigger) or "Unknown"
    if company and company != "Unknown":
        return company

    prompt = f"""
    Extract the company name from the following calendar event title.
    Ignore leading words like 'Firma', 'Company', 'Firma Dr.', 'Client'.
    Return only the clean company name as plain text (no quotes).
    If no company is found, return "Unknown".

    Title: "{title}"
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        result = response["choices"][0]["message"]["content"].strip()
        return result if result else "Unknown"
    except Exception:
        return "Unknown"

# Local JSONL sink without clashing with stdlib logging
_JSONL_PATH = Path(__file__).resolve().parents[1] / "logging" / "jsonl_sink.py"
_spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]
append_jsonl = _mod.append

_LOG_PATH = Path("logs") / "workflows" / "calendar.jsonl"


def _load_required_fields(source: str) -> List[str]:
    path = Path(__file__).resolve().parents[1] / "config" / "required_fields.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get(source, [])

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


def _int_from_env(name: str, default: int) -> int:
    """Return ``int(os.getenv(name, default))`` with a safe fallback."""
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


def _calendar_ids(primary_id: str) -> List[str]:
    """Return calendar IDs to poll.

    Currently limited to the primary calendar.  TODO: support multiple calendars
    (e.g. Google Workspace or additional accounts).
    """
    return [primary_id]


_PROCESSED_PATH = Path("logs") / "processed_events.jsonl"


def fetch_events(
    minutes_back: int | None = None,
    minutes_forward: int | None = None,
    calendar_id: str = "primary",
    max_results_per_page: int = 250,
) -> List[Dict[str, Any]]:
    """
    Return recent events from the given calendar filtered by trigger words.

    - Fails hard if trigger words are not configured or Google libs are missing.
    - Paginates through all results within the time window.
    """
    minutes_back = (
        minutes_back
        if minutes_back is not None
        else _int_from_env("CALENDAR_MINUTES_BACK", 10080)
    )
    minutes_forward = (
        minutes_forward
        if minutes_forward is not None
        else _int_from_env("CALENDAR_MINUTES_FWD", 86400)
    )

    filtered: List[Dict[str, Any]] = []
    total = 0
    processed = 0
    try:
        words = load_trigger_words()
        if not words:
            raise RuntimeError(
                "Google Calendar: no trigger words configured (core.trigger_words)"
            )

        now = _utc_now()
        time_min = (
            now - dt.timedelta(minutes=minutes_back)
        ).isoformat().replace("+00:00", "Z")
        time_max = (
            now + dt.timedelta(minutes=minutes_forward)
        ).isoformat().replace("+00:00", "Z")

        service = _service()

        for cid in _calendar_ids(calendar_id):
            page_token: Optional[str] = None
            while True:
                req = service.events().list(
                    calendarId=cid,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=max_results_per_page,
                    pageToken=page_token,
                )
                resp = req.execute()
                items: List[Dict[str, Any]] = resp.get("items", [])  # type: ignore[assignment]
                total += len(items)
                for ev in items:
                    uid = ev.get("id") or ev.get("iCalUID")
                    updated = ev.get("updated")
                    if not uid or not updated:
                        continue
                    if already_processed(uid, updated, _PROCESSED_PATH):
                        append_jsonl(
                            _LOG_PATH,
                            {
                                "timestamp": _utc_now().isoformat() + "Z",
                                "source": "calendar",
                                "status": "skipped",
                                "reason": "already_processed",
                                "id": uid,
                            },
                        )
                        continue
                    trigger = contains_trigger(ev, words)
                    if not trigger:
                        continue
                    description = ev.get("description") or ""
                    ev = dict(ev)
                    ev["detected_trigger"] = trigger
                    notes = {
                        "company": parser.extract_company(description),
                        "domain": parser.extract_domain(description),
                        "phone": parser.extract_phone(description),
                    }
                    comp_from_title = extract_company_ai(ev.get("summary", ""), trigger)
                    if comp_from_title and comp_from_title != "Unknown":
                        notes["company"] = comp_from_title
                    ev["notes_extracted"] = notes
                    ev["company_extracted"] = comp_from_title
                    filtered.append(ev)
                    processed += 1
                    mark_processed(uid, updated, _PROCESSED_PATH)
                    append_jsonl(
                        _LOG_PATH,
                        {
                            "timestamp": _utc_now().isoformat() + "Z",
                            "source": "calendar",
                            "status": "hit" if comp_from_title else "warning",
                            "company_extracted": comp_from_title,
                            "payload": ev,
                        },
                    )
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break

        append_jsonl(
            _LOG_PATH,
            {
                "timestamp": _utc_now().isoformat() + "Z",
                "source": "calendar",
                "status": "fetch",
                "calendar_id": calendar_id,
                "time_min": time_min,
                "time_max": time_max,
                "events_total": total,
                "events_new": processed,
            },
        )
    except Exception as e:
        append_jsonl(
            _LOG_PATH,
            {
                "timestamp": _utc_now().isoformat() + "Z",
                "source": "calendar",
                "status": "error",
                "error": str(e),
            },
        )
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
    required = _load_required_fields("calendar")
    optional = optional_fields()
    results: List[Dict[str, Any]] = []
    for ev in events:
        creator_info = ev.get("creator")
        organizer = ev.get("organizer") or {}
        creator_email = (
            (
                creator_info.get("email") if isinstance(creator_info, dict) else creator_info
            )
            or organizer.get("email")
            or ""
        )
        creator_name = (
            creator_info.get("displayName") if isinstance(creator_info, dict) else None
        )
        title = ev.get("summary") or "Untitled"
        description = ev.get("description") or ""
        notes = ev.get("notes_extracted") or {
            "company": parser.extract_company(description),
            "domain": parser.extract_domain(description),
            "phone": parser.extract_phone(description),
        }
        company = extract_company_ai(title, ev.get("detected_trigger", ""))
        if company == "Unknown":
            company = notes.get("company") or None
        start_raw = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
        end_raw = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date")
        try:
            start_dt = dt.datetime.fromisoformat(start_raw) if start_raw else None
        except Exception:
            start_dt = None
        try:
            end_dt = dt.datetime.fromisoformat(end_raw) if end_raw else None
        except Exception:
            end_dt = None

        normalized = {
            "title": title,
            "description": description,
            "company": company,
            "domain": notes.get("domain"),
            "email": creator_email,
            "phone": notes.get("phone"),
            "notes_extracted": notes,
            "event_id": ev.get("id"),
            "start_iso": start_raw,
            "end_iso": end_raw,
        }
        missing_req = [f for f in required if not normalized.get(f)]
        missing_opt = [f for f in optional if not normalized.get(f)]
        missing = missing_req + missing_opt
        if missing:
            email_sender.send_reminder(
                to=creator_email,
                creator_name=creator_name,
                creator_email=creator_email,
                event_id=ev.get("id"),
                event_title=normalized.get("title") or "",
                event_start=start_dt,
                event_end=end_dt,
                missing_fields=missing,
            )
        results.append(
            {
                "creator": creator_email,
                "trigger_source": "calendar",
                "recipient": creator_email,
                "payload": normalized,
            }
        )
    return results
