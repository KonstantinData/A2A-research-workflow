"""Integration tests for Google Calendar and Contacts modules."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import google_contacts


def test_contacts_scheduled_poll_integration(monkeypatch):
    contact = {
        "emailAddresses": [{"value": "bob@example.com"}],
        "names": [{"displayName": "Bob"}],
        "notes": "Firma Bar Inc\nbar.com\nResearch initiative\n+49 3333333",
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
                "notes_blob": "Firma Bar Inc\nbar.com\nResearch initiative\n+49 3333333",
                "notes_extracted": {
                    "company": "Bar Inc",
                    "domain": "bar.com",
                    "phone": "+49 3333333",
                },
            },
        }
    ]
