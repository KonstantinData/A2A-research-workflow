"""Tests for Google Calendar and Contacts scheduled polling."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import google_calendar, google_contacts  # noqa: E402
from core import trigger_words  # noqa: E402


def test_calendar_scheduled_poll_normalizes(monkeypatch):
    events = [{"creator": "alice@example.com", "summary": "Test"}]
    monkeypatch.setattr(google_calendar, "fetch_events", lambda: events)

    result = google_calendar.scheduled_poll()

    assert result == [
        {
            "creator": "alice@example.com",
            "trigger_source": "calendar",
            "recipient": "alice@example.com",
            "payload": events[0],
        }
    ]


def test_contacts_scheduled_poll_normalizes(monkeypatch):
    contacts = [
        {
            "emailAddresses": [{"value": "bob@example.com"}],
            "names": [],
            "notes": "research",
        }
    ]
    monkeypatch.setattr(google_contacts, "fetch_contacts", lambda: contacts)

    result = google_contacts.scheduled_poll()

    assert result == [
        {
            "creator": "bob@example.com",
            "trigger_source": "contacts",
            "recipient": "bob@example.com",
            "payload": contacts[0],
        }
    ]


def test_fetch_events_exits_early_when_no_triggers(tmp_path, monkeypatch):
    path = tmp_path / "triggers.txt"
    path.write_text("")
    monkeypatch.setenv("TRIGGER_WORDS_FILE", str(path))
    trigger_words.load_trigger_words.cache_clear()

    assert google_calendar.fetch_events() == []


def test_fetch_contacts_exits_early_when_no_triggers(tmp_path, monkeypatch):
    path = tmp_path / "triggers.txt"
    path.write_text("")
    monkeypatch.setenv("TRIGGER_WORDS_FILE", str(path))
    trigger_words.load_trigger_words.cache_clear()

    assert google_contacts.fetch_contacts() == []
