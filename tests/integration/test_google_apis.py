"""Integration tests for Google Calendar and Contacts modules."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import google_calendar, google_contacts


def test_calendar_scheduled_poll_integration(monkeypatch):
    events = [{"creator": "alice@example.com", "summary": "Demo"}]
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


def test_contacts_scheduled_poll_integration(monkeypatch):
    contacts = [
        {"emailAddresses": [{"value": "bob@example.com"}], "names": [], "notes": ""}
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
