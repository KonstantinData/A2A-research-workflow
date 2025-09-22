import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:  # pragma: no cover - guard legacy orchestrator stack
    from core import orchestrator, tasks, statuses
    # task_history removed - using event bus
except ImportError:  # pragma: no cover - legacy modules removed
    pytestmark = pytest.mark.skip(
        reason="Legacy workflow orchestrator removed; integration flow migrated"
    )
else:
    from agents import field_completion_agent, reminder_service
    from integrations import email_sender, email_client
    from config.settings import SETTINGS


@pytest.fixture(autouse=True)
def _setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "tasks.db"
    monkeypatch.setattr(tasks, "DB_PATH", db_path)



def _stub_pdf(data, path):
    path.write_text("pdf")


def _stub_csv(data, path):
    path.write_text("csv")


def _collect_logs() -> str:
    return "".join(p.read_text() for p in sorted(SETTINGS.workflows_dir.glob("*.jsonl")))


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
    orchestrator.log_event({"event_id": "e1", "status": statuses.PENDING})
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
    assert '"status": "enriched_by_ai"' in logs
    assert '"status": "fields_missing"' not in logs
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
    assert f'"status": "{statuses.PENDING}"' in logs
    assert len(send_calls) == 1  # Only reminder email, no report email without company data
    subjects = {c["subject"] for c in send_calls}
    assert "Missing Information Required - A2A Research (Task: e3)" in subjects
    # No report email should be sent when company data is missing
    assert "Your A2A research report" not in subjects


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
    assert '"status": "resumed"' in logs


def test_reminder_and_escalation(monkeypatch):
    events = []

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


def test_existing_report_prompt(monkeypatch):
    trig = {
        "source": "calendar",
        "creator": "a@b",
        "recipient": "a@b",
        "payload": {"event_id": "e6", "company_name": "ACME", "domain": "acme.com"},
    }
    send_calls = []
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda **k: send_calls.append(k))
    monkeypatch.setattr(orchestrator.email_reader, "fetch_replies", lambda: [{"creator": "a@b", "text": "Nein"}])
    orchestrator.run(
        triggers=[trig],
        researchers=[],
        consolidate_fn=lambda r: {},
        pdf_renderer=_stub_pdf,
        csv_exporter=_stub_csv,
        hubspot_upsert=lambda d: None,
        hubspot_attach=lambda p, c: None,
        hubspot_check_existing=lambda cid: {"id": "1"},
    )
    logs = _collect_logs()
    assert '"status": "report_exists_query"' in logs
    assert '"status": "report_skipped"' in logs
    assert send_calls


def test_existing_report_continue(monkeypatch):
    trig = {
        "source": "calendar",
        "creator": "a@b",
        "recipient": "a@b",
        "payload": {"event_id": "e7", "company_name": "ACME", "domain": "acme.com"},
    }
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda **k: None)
    monkeypatch.setattr(orchestrator.email_reader, "fetch_replies", lambda: [{"creator": "a@b", "text": "Ja"}])
    orchestrator.run(
        triggers=[trig],
        researchers=[],
        consolidate_fn=lambda r: {},
        pdf_renderer=_stub_pdf,
        csv_exporter=_stub_csv,
        hubspot_upsert=lambda d: None,
        hubspot_attach=lambda p, c: None,
        hubspot_check_existing=lambda cid: {"id": "1"},
    )
    logs = _collect_logs()
    assert '"status": "report_exists_query"' in logs
    assert '"status": "report_skipped"' not in logs
