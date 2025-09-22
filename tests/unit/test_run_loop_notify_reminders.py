import pytest

try:  # pragma: no cover - guard legacy run loop
    from core import run_loop
except ImportError:  # pragma: no cover - module removed
    pytestmark = pytest.mark.skip(
        reason="Legacy run_loop removed; reminder notifications moved"
    )


class DummyReminder:
    def __init__(self):
        self.triggers = []

    def check_and_notify(self, triggers):
        self.triggers.extend(triggers)


def test_notify_reminders_handles_partial_missing():
    reminder = DummyReminder()
    trigger = {
        "payload": {"event_id": "e1", "company_name": "ACME"},
    }

    run_loop.notify_reminders([trigger], reminder_service=reminder)

    assert reminder.triggers
    assert reminder.triggers[0]["missing"] == ["domain"]


def test_notify_reminders_skips_complete_triggers():
    reminder = DummyReminder()
    trigger = {
        "payload": {"event_id": "e2", "company_name": "ACME", "domain": "acme.com"},
    }

    run_loop.notify_reminders([trigger], reminder_service=reminder)

    assert reminder.triggers == []
