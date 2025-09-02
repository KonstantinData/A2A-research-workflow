import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator, statuses


def test_gather_triggers_logs_discard_reasons(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    events = [
        {"id": "1", "event_id": "1", "summary": "No trigger here"},
        {"id": "2", "event_id": "2", "summary": "Research meeting"},
    ]
    monkeypatch.setattr(orchestrator, "fetch_events", lambda: events)
    monkeypatch.setattr(orchestrator, "fetch_contacts", lambda: [])
    monkeypatch.setattr(orchestrator, "_calendar_fetch_logged", lambda wf_id: None)
    monkeypatch.setattr(orchestrator, "_contacts_fetch_logged", lambda wf_id: None)

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
    assert any(r.get("status") == statuses.NOT_RELEVANT and r.get("event_id") == "1" for r in wf_records)


def test_gather_triggers_logs_no_calendar_events(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(orchestrator, "fetch_events", lambda: [])
    monkeypatch.setattr(orchestrator, "fetch_contacts", lambda: [])
    monkeypatch.setattr(orchestrator, "_calendar_fetch_logged", lambda wf_id: None)
    monkeypatch.setattr(orchestrator, "_contacts_fetch_logged", lambda wf_id: None)
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
    monkeypatch.setattr(orchestrator, "_calendar_fetch_logged", lambda wf_id: None)
    monkeypatch.setattr(orchestrator, "_contacts_fetch_logged", lambda wf_id: None)
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
        records.append({"event_id": event_id, "status": statuses.NEEDS_ADMIN_FIX})

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
    assert any(r.get("status") == statuses.NEEDS_ADMIN_FIX for r in records)


def test_fetch_functions_log_ingested(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    records = []
    monkeypatch.setattr(orchestrator, "log_event", lambda r: records.append(r))

    def fake_fetch_events():
        orchestrator.log_event({"event_id": "e1", "status": "ingested"})
        return [{"event_id": "e1", "summary": "Research meeting"}]

    def fake_fetch_contacts():
        orchestrator.log_event({"event_id": "c1", "status": "ingested"})
        return [{"resourceName": "c1", "emailAddresses": [{"value": "a@b"}]}]

    monkeypatch.setattr(orchestrator, "fetch_events", fake_fetch_events)
    monkeypatch.setattr(orchestrator, "fetch_contacts", fake_fetch_contacts)
    monkeypatch.setattr(orchestrator, "_calendar_fetch_logged", lambda wf_id: None)
    monkeypatch.setattr(orchestrator, "_contacts_fetch_logged", lambda wf_id: None)

    orchestrator.gather_triggers()

    assert any(r.get("status") == "ingested" and r.get("event_id") == "e1" for r in records)
    assert any(r.get("status") == "ingested" and r.get("event_id") == "c1" for r in records)


@pytest.mark.parametrize(
    "code,expected",
    [
        ("missing", "calendar_fetch_missing"),
        ("missing_client", "calendar_fetch_missing_client"),
        ("oauth_error", "calendar_fetch_oauth_error"),
    ],
)
def test_gather_triggers_logs_calendar_fetch_codes(tmp_path, monkeypatch, code, expected):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(orchestrator, "fetch_events", lambda: [])
    monkeypatch.setattr(orchestrator, "fetch_contacts", lambda: [])
    monkeypatch.setattr(orchestrator, "_calendar_fetch_logged", lambda wf_id: code)
    monkeypatch.setattr(orchestrator, "_contacts_fetch_logged", lambda wf_id: None)
    records = []
    monkeypatch.setattr(orchestrator, "log_event", lambda r: records.append(r))
    orchestrator.gather_triggers()
    assert any(r.get("status") == expected for r in records)


@pytest.mark.parametrize(
    "code,expected",
    [
        ("missing", "contacts_fetch_missing"),
        ("missing_client", "contacts_fetch_missing_client"),
        ("oauth_error", "contacts_fetch_oauth_error"),
    ],
)
def test_gather_triggers_logs_contacts_fetch_codes(tmp_path, monkeypatch, code, expected):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(orchestrator, "fetch_events", lambda: [])
    monkeypatch.setattr(orchestrator, "fetch_contacts", lambda: [])
    monkeypatch.setattr(orchestrator, "_calendar_fetch_logged", lambda wf_id: None)
    monkeypatch.setattr(orchestrator, "_contacts_fetch_logged", lambda wf_id: code)
    records = []
    monkeypatch.setattr(orchestrator, "log_event", lambda r: records.append(r))
    orchestrator.gather_triggers()
    assert any(r.get("status") == expected for r in records)
