import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator, tasks, task_history
from agents import field_completion_agent, reminder_service
from integrations import email_sender, email_client


@pytest.fixture(autouse=True)
def _setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "tasks.db"
    monkeypatch.setattr(tasks, "DB_PATH", db_path)
    monkeypatch.setattr(task_history, "DB_PATH", db_path)


def _stub_pdf(data, path):
    path.write_text("pdf")


def _stub_csv(data, path):
    path.write_text("csv")


def _collect_logs() -> str:
    return "".join(p.read_text() for p in sorted(Path("logs/workflows").glob("*.jsonl")))


def _orchestrator_run(triggers, monkeypatch):
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)
    try:
        orchestrator.run(
            triggers=triggers,
            researchers=[],
            consolidate_fn=lambda r: {},
            pdf_renderer=_stub_pdf,
            csv_exporter=_stub_csv,
            hubspot_upsert=lambda d: None,
            hubspot_attach=lambda p, c: None,
            hubspot_check_existing=lambda cid: None,
        )
    except SystemExit:
        pass


def test_duplicate_event_logged(monkeypatch):
    trig = {
        "source": "calendar",
        "creator": "a@b",
        "recipient": "a@b",
        "payload": {
            "event_id": "e1",
            "company_name": "ACME",
            "domain": "acme.com",
        },
    }
    _orchestrator_run([trig], monkeypatch)
    _orchestrator_run([trig], monkeypatch)
    logs = _collect_logs()
    assert '"status": "duplicate_event"' in logs


def test_ai_enrichment_success(monkeypatch):
    monkeypatch.setattr(field_completion_agent, "run", lambda t: {"company_name": "ACME", "domain": "acme.com"})
    send_calls = []
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: send_calls.append(k))
    trig = {
        "source": "calendar",
        "creator": "a@b",
        "recipient": "a@b",
        "payload": {"event_id": "e2"},
    }
    orchestrator.run(
        triggers=[trig],
        researchers=[],
        consolidate_fn=lambda r: {},
        pdf_renderer=_stub_pdf,
        csv_exporter=_stub_csv,
        hubspot_upsert=lambda d: None,
        hubspot_attach=lambda p, c: None,
        hubspot_check_existing=lambda cid: None,
    )
    logs = _collect_logs()
    assert '"status": "fields_missing"' in logs
    assert '"status": "enriched_by_ai"' in logs
    assert not any("Missing Information" in c.get("subject", "") for c in send_calls)


def test_ai_failure_triggers_email(monkeypatch):
    monkeypatch.setattr(field_completion_agent, "run", lambda t: {})
    send_calls = []
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: send_calls.append(k))
    trig = {
        "source": "calendar",
        "creator": "a@b",
        "recipient": "a@b",
        "payload": {"event_id": "e3"},
    }
    orchestrator.run(
        triggers=[trig],
        researchers=[],
        consolidate_fn=lambda r: {},
        pdf_renderer=_stub_pdf,
        csv_exporter=_stub_csv,
        hubspot_upsert=lambda d: None,
        hubspot_attach=lambda p, c: None,
        hubspot_check_existing=lambda cid: None,
    )
    logs = _collect_logs()
    assert '"status": "missing_fields_pending"' in logs
    assert len(send_calls) == 1
    assert send_calls[0]["subject"] == "Your A2A research report"


def test_email_reply_resumes(monkeypatch):
    task = tasks.create_task("e4", ["domain"], "user@condata.io")
    monkeypatch.setattr(field_completion_agent, "run", lambda t: {})
    monkeypatch.setattr(
        orchestrator.email_reader,
        "fetch_replies",
        lambda: [{"creator": "user@condata.io", "task_id": task["id"], "fields": {"domain": "acme.com"}, "event_id": "e4"}],
    )
    trig = {
        "source": "calendar",
        "creator": "user@condata.io",
        "recipient": "user@condata.io",
        "payload": {"event_id": "e4", "company_name": "ACME", "task_id": task["id"]},
    }
    orchestrator.run(
        triggers=[trig],
        researchers=[],
        consolidate_fn=lambda r: {},
        pdf_renderer=_stub_pdf,
        csv_exporter=_stub_csv,
        hubspot_upsert=lambda d: None,
        hubspot_attach=lambda p, c: None,
        hubspot_check_existing=lambda cid: None,
    )
    logs = _collect_logs()
    assert '"status": "email_reply_received"' in logs
    assert '"status": "pending_email_reply_resolved"' in logs


def test_reminder_and_escalation(monkeypatch):
    events = []
    monkeypatch.setattr(task_history, "record_event", lambda tid, ev: events.append((tid, ev)))
    monkeypatch.setattr(task_history, "has_event_since", lambda tid, ev, since: (tid, ev) in events)
    reminder_calls = []
    escalate_calls = []
    monkeypatch.setattr(email_client, "send_email", lambda to, fields, task_id=None: reminder_calls.append({"to": to, "task_id": task_id}))
    monkeypatch.setattr(email_sender, "send_email", lambda **k: escalate_calls.append(k))
    tasks.create_task("e5", ["domain"], "user@condata.io")
    scheduler = reminder_service.ReminderScheduler()
    scheduler.send_reminders()
    scheduler.escalate_tasks()
    logs = _collect_logs()
    assert reminder_calls and reminder_calls[0]["to"] == "user@condata.io"
    assert escalate_calls and escalate_calls[0]["to"] == "admin@condata.io"
    assert '"status": "reminder_sent"' in logs
    assert '"status": "escalation_sent"' in logs
