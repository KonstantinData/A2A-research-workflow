"""Tests for Google Calendar and Contacts scheduled polling."""

from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import google_contacts  # noqa: E402
from core import trigger_words  # noqa: E402


def test_contacts_scheduled_poll_normalizes(monkeypatch):
    contact = {
        "emailAddresses": [{"value": "bob@example.com"}],
        "names": [{"displayName": "Bob"}],
        "notes": "Firma ACME Corp\nacme.com\n+49 987654321",
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
                "company": "ACME Corp",
                "domain": "acme.com",
                "email": "bob@example.com",
                "phone": "+49 987654321",
                "notes_extracted": {
                    "company": "ACME Corp",
                    "domain": "acme.com",
                    "phone": "+49 987654321",
                },
            },
        }
    ]


def test_contacts_scheduled_poll_summarizes_notes(monkeypatch):
    """Summary field added when feature flag enabled."""
    contact = {
        "emailAddresses": [{"value": "bob@example.com"}],
        "names": [{"displayName": "Bob"}],
        "notes": "Bob is great. Loves testing.\nFirma Foo\nfoo.com\n+49 1111111",
    }

    monkeypatch.setattr(google_contacts, "fetch_contacts", lambda: [contact])
    monkeypatch.setattr(google_contacts.feature_flags, "ENABLE_SUMMARY", True)
    monkeypatch.setattr(google_contacts.email_sender, "send", lambda *a, **k: None)

    result = google_contacts.scheduled_poll()

    assert result[0]["payload"]["summary"] == "Bob is great"


def test_contacts_poll_falls_back_to_admin(monkeypatch):
    """If a contact has no e-mail address, admin is notified."""
    contact = {
        "names": [{"displayName": "Bob"}],
        "notes": "Firma ACME",  # missing domain triggers reminder
    }
    monkeypatch.setattr(google_contacts, "fetch_contacts", lambda: [contact])
    sent = {}
    monkeypatch.setattr(google_contacts.email_sender, "send", lambda **k: sent.update(k))

    google_contacts.scheduled_poll()

    assert sent.get("to") == "admin@condata.io"


def test_fetch_contacts_exits_early_when_no_triggers(tmp_path, monkeypatch):
    path = tmp_path / "triggers.txt"
    path.write_text("")
    monkeypatch.setenv("TRIGGER_WORDS_FILE", str(path))
    trigger_words.load_trigger_words.cache_clear()

    with pytest.raises(RuntimeError):
        google_contacts.fetch_contacts()
