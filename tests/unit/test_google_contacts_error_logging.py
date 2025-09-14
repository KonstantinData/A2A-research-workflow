from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import google_contacts
from core import orchestrator


def test_fetch_contacts_logs_when_api_client_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIVE_MODE", "0")
    records = []
    monkeypatch.setattr(orchestrator, "log_event", lambda r: records.append(r))
    monkeypatch.setattr(google_contacts, "build", None)
    monkeypatch.setattr(google_contacts, "Request", None)

    contacts = google_contacts.fetch_contacts()
    assert contacts == []
    assert any(r.get("status") == "google_api_client_missing" for r in records)


def test_gather_triggers_logs_no_contacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIVE_MODE", "0")
    records = []
    monkeypatch.setattr(orchestrator, "log_event", lambda r: records.append(r))
    monkeypatch.setattr(orchestrator, "fetch_events", lambda: [])
    monkeypatch.setattr(orchestrator, "fetch_contacts", lambda: [])
    monkeypatch.setattr(orchestrator, "_calendar_fetch_logged", lambda wf_id: None)
    monkeypatch.setattr(orchestrator, "_contacts_fetch_logged", lambda wf_id: None)

    triggers = orchestrator.gather_triggers()
    assert triggers == []
    assert any(r.get("status") == "no_contacts" for r in records)


def test_fetch_contacts_raises_when_api_client_missing_live_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIVE_MODE", "1")
    monkeypatch.setattr(google_contacts, "build", None)
    monkeypatch.setattr(google_contacts, "Request", None)
    with pytest.raises(RuntimeError):
        google_contacts.fetch_contacts()
