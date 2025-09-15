from pathlib import Path
import sys
from datetime import datetime, time as dtime

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.reminder_service import ReminderScheduler, check_and_notify
from core import tasks, task_history, statuses
from core.utils import get_workflow_id
from integrations import email_client, email_sender
from config.settings import SETTINGS
import json


@pytest.fixture(autouse=True)
def _db_tmp(monkeypatch, tmp_path):
    monkeypatch.setenv("TASKS_DB_PATH", str(tmp_path / "tasks.db"))
    # ensure modules use new DB path
    import importlib
    importlib.reload(tasks)
    importlib.reload(task_history)
    yield
    importlib.reload(tasks)
    importlib.reload(task_history)


def test_send_reminders_records_history(monkeypatch):
    calls = []

    def fake_send(email, fields, task_id=None):
        calls.append((email, fields, task_id))

    monkeypatch.setattr(email_client, "send_email", fake_send)

    task = tasks.create_task("trigger", ["field"], "user@example.com")

    scheduler = ReminderScheduler()
    scheduler.send_reminders()

    assert calls and calls[0][0] == "user@example.com"
    today = datetime.combine(datetime.now().date(), dtime.min)
    assert task_history.has_event_since(task["id"], "reminder_sent", today)
    assert tasks.get_task(task["id"])["status"] == "reminded"


def test_escalate_tasks_emails_admin(monkeypatch):
    calls = []

    def fake_send(*, to, subject, body, sender=None, attachments=None, task_id=None):
        calls.append({
            "sender": sender,
            "recipient": to,
            "subject": subject,
            "body": body,
            "task_id": task_id,
        })

    monkeypatch.setenv("MAIL_FROM", "bot@example.com")
    monkeypatch.setattr(email_sender, "send_email", fake_send)

    task = tasks.create_task("trigger", ["field"], "user@example.com")
    task_history.record_event(task["id"], "reminder_sent")

    scheduler = ReminderScheduler()
    scheduler.escalate_tasks()

    assert calls and calls[0]["recipient"] == "admin@condata.io"
    today = datetime.combine(datetime.now().date(), dtime.min)
    assert task_history.has_event_since(task["id"], "escalated", today)
    assert tasks.get_task(task["id"])["status"] == "escalated"


def test_scheduler_run_flow(monkeypatch):
    reminder_calls = []
    escalation_calls = []

    def fake_reminder(email, fields, task_id=None):
        reminder_calls.append(task_id)

    def fake_escalation(*, to, subject, body, sender=None, attachments=None, task_id=None):
        escalation_calls.append(task_id)

    monkeypatch.setattr(email_client, "send_email", fake_reminder)
    monkeypatch.setattr(email_sender, "send_email", fake_escalation)

    task = tasks.create_task("trigger", ["field"], "user@example.com")

    scheduler = ReminderScheduler()

    times = [
        datetime(2023, 1, 1, 9, 0),
        datetime(2023, 1, 1, 10, 0),
        datetime(2023, 1, 1, 15, 0),
    ]

    def fake_now():
        if times:
            return times.pop(0)
        raise KeyboardInterrupt

    monkeypatch.setattr(scheduler, "_now", fake_now)

    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(ReminderScheduler, "_sleep", lambda self, s: fake_sleep(s))

    with pytest.raises(KeyboardInterrupt):
        scheduler.run_forever()

    assert reminder_calls == [task["id"]]
    assert escalation_calls == [task["id"]]
    assert sleep_calls == [3600, 18000]
    assert tasks.get_task(task["id"])["status"] == "escalated"


def test_check_and_notify_logs(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    wf_id = get_workflow_id()
    log_dir = SETTINGS.workflows_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{wf_id}.jsonl"
    entries = [
        {"event_id": "e1", "status": statuses.PENDING},
        {"event_id": "e2", "status": "done"},
        {"event_id": "e3", "status": statuses.PENDING_ADMIN},
    ]
    with log_path.open("w", encoding="utf-8") as fh:
        for rec in entries:
            fh.write(json.dumps(rec) + "\n")

    calls = []

    def fake_send(*, to, subject, body):
        calls.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr(email_sender, "send", fake_send)

    triggers = [
        {
            "source": "calendar",
            "recipient": "a@example.com",
            "missing": ["domain"],
            "payload": {"event_id": "e1"},
        },
        {
            "source": "calendar",
            "recipient": "b@example.com",
            "missing": ["domain"],
            "payload": {"event_id": "e2"},
        },
        {
            "source": "contacts",
            "recipient": "c@example.com",
            "missing": ["domain"],
            "payload": {"event_id": "e3"},
        },
    ]

    check_and_notify(triggers)

    assert {c["to"] for c in calls} == {"a@example.com", "c@example.com"}
    reminder_log = SETTINGS.workflows_dir / "reminders.jsonl"
    lines = reminder_log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        rec = json.loads(line)
        assert rec["status"] == "reminder_sent"
