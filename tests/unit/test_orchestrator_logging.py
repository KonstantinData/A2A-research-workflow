import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator


def test_gather_triggers_logs_discard_reasons(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    events = [
        {"id": "1", "event_id": "1", "summary": "No trigger here"},
        {"id": "2", "event_id": "2", "summary": "Research meeting"},
    ]
    monkeypatch.setattr(orchestrator, "fetch_events", lambda: events)
    monkeypatch.setattr(orchestrator, "fetch_contacts", lambda: [])
    monkeypatch.setattr(orchestrator, "_calendar_fetch_logged", lambda wf_id: True)

    triggers = orchestrator.gather_triggers()
    assert triggers == []

    log_file = Path("logs") / "workflows" / "calendar.jsonl"
    records = [json.loads(line) for line in log_file.read_text().splitlines()]
    reasons = [r.get("reason") for r in records if r.get("status") == "event_discarded"]
    assert "no_trigger_match" in reasons
    assert "missing_fields" in reasons


def test_gather_triggers_logs_no_calendar_events(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(orchestrator, "fetch_events", lambda: [])
    monkeypatch.setattr(orchestrator, "fetch_contacts", lambda: [])
    monkeypatch.setattr(orchestrator, "_calendar_fetch_logged", lambda wf_id: True)
    records = []
    monkeypatch.setattr(orchestrator, "log_event", lambda r: records.append(r))

    triggers = orchestrator.gather_triggers()
    assert triggers == []
    assert any(r.get("status") == "no_calendar_events" for r in records)
