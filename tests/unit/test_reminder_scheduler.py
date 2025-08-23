from pathlib import Path
import sys
from datetime import datetime, time as dtime

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.reminder_service import ReminderScheduler
from core import tasks, task_history
from integrations import email_client, email_sender


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

    def fake_send(email, fields):
        calls.append((email, fields))

    monkeypatch.setattr(email_client, "send_email", fake_send)

    task = tasks.create_task("trigger", ["field"], "user@example.com")

    scheduler = ReminderScheduler()
    scheduler.send_reminders()

    assert calls and calls[0][0] == "user@example.com"
    today = datetime.combine(datetime.now().date(), dtime.min)
    assert task_history.has_event_since(task["id"], "reminder_sent", today)


def test_escalate_tasks_emails_admin(monkeypatch):
    calls = []

    def fake_send(sender, recipient, subject, body, attachments=None):
        calls.append({
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "body": body,
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
