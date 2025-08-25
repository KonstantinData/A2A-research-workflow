# integrations/google_calendar.py
"""Google Calendar integration (LIVE, strict env, no silent fallbacks)."""
from __future__ import annotations

import datetime as dt
import importlib.util as _ilu
import json
import os
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
from core.utils import normalize_text
from core import parser
from . import email_sender


def contains_trigger(text: str, trigger_words: list[str]) -> bool:
    text = normalize_text(text)
    return any(normalize_text(t) in text for t in trigger_words)

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


def fetch_events(
    minutes_back: int = 30,
    minutes_forward: int = 120,
    calendar_id: str = "primary",
    max_results_per_page: int = 250,
) -> List[Dict[str, Any]]:
    """
    Return recent events from the given calendar filtered by trigger words.

    - Fails hard if trigger words are not configured or Google libs are missing.
    - Paginates through all results within the time window.
    """
    filtered: List[Dict[str, Any]] = []
    try:
        words = load_trigger_words()
        if not words:
            raise RuntimeError(
                "Google Calendar: no trigger words configured (core.trigger_words)"
            )

        now = _utc_now()
        time_min = (now - dt.timedelta(minutes=minutes_back)).isoformat()
        time_max = (now + dt.timedelta(minutes=minutes_forward)).isoformat()

        service = _service()

        page_token: Optional[str] = None
        while True:
            req = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=max_results_per_page,
                pageToken=page_token,
            )
            resp = req.execute()
            items: List[Dict[str, Any]] = resp.get("items", [])  # type: ignore[assignment]
            for ev in items:
                summary = ev.get("summary") or ""
                description = ev.get("description") or ""
                content = f"{summary}\n{description}"
                if contains_trigger(content, words):
                    ev = dict(ev)
                    notes = {
                        "company": parser.extract_company(description),
                        "domain": parser.extract_domain(description),
                        "phone": parser.extract_phone(description),
                    }
                    ev["notes_extracted"] = notes
                    filtered.append(ev)
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
