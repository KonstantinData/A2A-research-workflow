import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import google_calendar
from core import orchestrator


def test_fetch_events_logs_when_api_client_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIVE_MODE", "0")
    records = []
    monkeypatch.setattr(orchestrator, "log_event", lambda r: records.append(r))
    monkeypatch.setattr(google_calendar, "build", None)
    monkeypatch.setattr(google_calendar, "Credentials", None)

    events = google_calendar.fetch_events()
    assert events == []
    assert any(r.get("status") == "google_api_client_missing" for r in records)


def test_fetch_events_logs_when_oauth_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIVE_MODE", "0")
    records = []
    monkeypatch.setattr(orchestrator, "log_event", lambda r: records.append(r))
    monkeypatch.setattr(google_calendar, "build", object())
    monkeypatch.setattr(google_calendar, "Credentials", object)
    monkeypatch.setattr(google_calendar, "build_user_credentials", lambda scopes: None)

    events = google_calendar.fetch_events()
    assert events == []
    assert any(r.get("status") == "missing_google_oauth_env" for r in records)


def test_gather_triggers_mirrors_calendar_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIVE_MODE", "0")
    records = []
    monkeypatch.setattr(orchestrator, "log_event", lambda r: records.append(r))
    monkeypatch.setattr(orchestrator, "fetch_events", lambda: [])
    monkeypatch.setattr(orchestrator, "fetch_contacts", lambda: [])
    monkeypatch.setattr(orchestrator, "_calendar_fetch_logged", lambda wf_id: None)
    monkeypatch.setattr(orchestrator, "_contacts_fetch_logged", lambda wf_id: None)

    orchestrator.log_step(
        "calendar", "fetch_error", {"error": "boom"}, severity="error"
    )

    triggers = orchestrator.gather_triggers()
    assert triggers == []
    assert any(r.get("status") == "fetch_error" and r.get("error") == "boom" for r in records)


def test_fetch_events_raises_when_api_client_missing_live_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIVE_MODE", "1")
    monkeypatch.setattr(google_calendar, "build", None)
    monkeypatch.setattr(google_calendar, "Credentials", None)
    with pytest.raises(RuntimeError):
        google_calendar.fetch_events()
