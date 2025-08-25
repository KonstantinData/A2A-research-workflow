"""Integration tests for Google Calendar and Contacts modules."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import google_calendar, google_contacts


def test_calendar_scheduled_poll_integration(monkeypatch):
    event = {
        "creator": {"email": "alice@example.com"},
        "summary": "Demo",
        "description": "Firma DemoCorp\ndemocorp.com\n+49 2222222",
    }
    monkeypatch.setattr(google_calendar, "fetch_events", lambda: [event])
    monkeypatch.setattr(google_calendar.email_sender, "send", lambda *a, **k: None)

    result = google_calendar.scheduled_poll()

    assert result == [
        {
            "creator": "alice@example.com",
            "trigger_source": "calendar",
            "recipient": "alice@example.com",
            "payload": {
                "title": "Demo",
                "description": "Firma DemoCorp\ndemocorp.com\n+49 2222222",
                "company": "DemoCorp",
                "domain": "democorp.com",
                "email": "alice@example.com",
                "phone": "+49 2222222",
                "notes_extracted": {
                    "company": "DemoCorp",
                    "domain": "democorp.com",
                    "phone": "+49 2222222",
                },
            },
        }
    ]


def test_contacts_scheduled_poll_integration(monkeypatch):
    contact = {
        "emailAddresses": [{"value": "bob@example.com"}],
        "names": [{"displayName": "Bob"}],
        "notes": "Firma Bar Inc\nbar.com\n+49 3333333",
    }
    monkeypatch.setattr(google_contacts, "fetch_contacts", lambda: [contact])
    monkeypatch.setattr(google_contacts.email_sender, "send", lambda *a, **k: None)

    result = google_contacts.scheduled_poll()

    assert result == [
        {
            "creator": "bob@example.com",
            "trigger_source": "contacts",
            "recipient": "bob@example.com",
            "payload": {
                "names": ["Bob"],
                "company": "Bar Inc",
                "domain": "bar.com",
                "email": "bob@example.com",
                "phone": "+49 3333333",
                "notes_extracted": {
                    "company": "Bar Inc",
                    "domain": "bar.com",
                    "phone": "+49 3333333",
                },
            },
        }
    ]
