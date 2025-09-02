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
    assert len(triggers) == 1
    assert triggers[0]["payload"]["event_id"] == "2"

    log_file = Path("logs") / "workflows" / "calendar.jsonl"
    records = [json.loads(line) for line in log_file.read_text().splitlines()]
    reasons = [r.get("reason") for r in records if r.get("status") == "event_discarded"]
    assert "no_trigger_match" in reasons
    assert "missing_fields" not in reasons

    wf_log = next((Path("logs") / "workflows").glob("wf-*.jsonl"))
    wf_records = [json.loads(line) for line in wf_log.read_text().splitlines()]
    assert any(r.get("status") == "not_relevant" and r.get("event_id") == "1" for r in wf_records)


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


def test_gather_triggers_logs_contacts_fetch_failed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(orchestrator, "fetch_events", lambda: [])

    def raise_env_error():
        raise RuntimeError("Missing Google OAuth env")

    monkeypatch.setattr(orchestrator, "fetch_contacts", raise_env_error)
    monkeypatch.setattr(orchestrator, "_calendar_fetch_logged", lambda wf_id: True)
    records = []
    monkeypatch.setattr(orchestrator, "log_event", lambda r: records.append(r))

    triggers = orchestrator.gather_triggers()
    assert triggers == []
    assert any(r.get("status") == "contacts_fetch_failed" for r in records)


def test_run_invokes_recovery_on_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    records = []
    monkeypatch.setattr(orchestrator, "log_event", lambda r: records.append(r))
    monkeypatch.setattr(orchestrator.reminder_service, "check_and_notify", lambda triggers: None)

    called = {}

    def fake_handle_failure(event_id, error):
        called["event_id"] = event_id
        records.append({"event_id": event_id, "status": "needs_admin_fix"})

    monkeypatch.setattr(orchestrator.recovery_agent, "handle_failure", fake_handle_failure)

    def fail_hubspot(data):
        raise RuntimeError("boom")

    trig = [{"payload": {"event_id": "42", "company_name": "Acme", "domain": "acme.com"}}]

    orchestrator.run(
        triggers=trig,
        researchers=[],
        pdf_renderer=lambda d, p: None,
        csv_exporter=lambda d, p: None,
        hubspot_upsert=fail_hubspot,
        hubspot_attach=lambda p, c: None,
        hubspot_check_existing=lambda c: None,
        duplicate_checker=lambda d, e: False,
        company_id=None,
    )

    assert called["event_id"] == "42"
    assert any(r.get("status") == "needs_admin_fix" for r in records)
