# integrations/google_calendar.py
"""Google Calendar integration (LIVE, strict env, no silent fallbacks)."""
from __future__ import annotations

import datetime as dt
import importlib.util as _ilu
import json
import os
import re
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
from core.utils import normalize_text, already_processed, mark_processed
from core import parser
from . import email_sender


def contains_trigger(event: dict, trigger_words: list[str]) -> bool:
    title = normalize_text(event.get("summary", ""))
    desc = normalize_text(event.get("description", ""))
    for t in trigger_words:
        t_norm = normalize_text(t)
        if t_norm in title or t_norm in desc:
            return True
    return False


def _extract_company_from_title(title: str, trigger_words: list[str]) -> Optional[str]:
    """If the title starts with a trigger word, return the remaining text as company."""
    if not title:
        return None
    title_norm = normalize_text(title)
    for t in trigger_words:
        t_norm = normalize_text(t)
        if title_norm.startswith(t_norm):
            rest = title[len(t):].strip(" -:–—")
            rest = re.sub(r"\b(firma|company)\b", "", rest, flags=re.IGNORECASE).strip()
            return rest or None
    return None

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
                    if not contains_trigger(ev, words):
                        continue
                    description = ev.get("description") or ""
                    ev = dict(ev)
                    notes = {
                        "company": parser.extract_company(description),
                        "domain": parser.extract_domain(description),
                        "phone": parser.extract_phone(description),
                    }
                    comp_from_title = _extract_company_from_title(ev.get("summary", ""), words)
                    if comp_from_title:
                        notes["company"] = comp_from_title
                    ev["notes_extracted"] = notes
                    filtered.append(ev)
                    processed += 1
                    mark_processed(uid, updated, _PROCESSED_PATH)
                    append_jsonl(
                        _LOG_PATH,
                        {
                            "timestamp": _utc_now().isoformat() + "Z",
                            "source": "calendar",
                            "status": "hit",
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
    results: List[Dict[str, Any]] = []
    for ev in events:
        creator_info = ev.get("creator")
        organizer = ev.get("organizer") or {}
        creator_email = (
            (
                creator_info.get("email")
                if isinstance(creator_info, dict)
                else creator_info
            )
            or organizer.get("email")
            or ""
        )
        description = ev.get("description") or ""
        notes = ev.get("notes_extracted") or {
            "company": parser.extract_company(description),
            "domain": parser.extract_domain(description),
            "phone": parser.extract_phone(description),
        }
        payload = {
            "title": ev.get("summary") or "",
            "description": description,
            "company": notes.get("company"),
            "domain": notes.get("domain"),
            "email": creator_email,
            "phone": notes.get("phone"),
            "notes_extracted": notes,
        }
        missing = [f for f in required if not payload.get(f)]
        if missing:
            body = (
                "Please provide the following missing fields: " + ", ".join(missing)
            )
            email_sender.send(
                to=creator_email,
                subject="Information missing for calendar entry",
                body=body,
            )
        results.append(
            {
                "creator": creator_email,
                "trigger_source": "calendar",
                "recipient": creator_email,
                "payload": payload,
            }
        )
    return results
