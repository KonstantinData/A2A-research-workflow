"""Tests for Google Calendar and Contacts scheduled polling."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import google_contacts  # noqa: E402


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
                "notes_blob": "Firma ACME Corp\nacme.com\n+49 987654321",
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


def test_fetch_contacts_missing_creds_logs(monkeypatch):
    logs = []
    monkeypatch.setattr(google_contacts, "build", object())
    monkeypatch.setattr(google_contacts, "Request", object)
    monkeypatch.setattr(google_contacts, "build_user_credentials", lambda scopes: None)
    monkeypatch.setattr(google_contacts, "log_step", lambda *a, **k: logs.append((a, k)))

    assert google_contacts.fetch_contacts() == []
    assert any(args[1] == "missing_google_oauth_env" for args, _ in logs)


def test_contacts_scheduled_poll_requests_confirmation_on_similar_trigger(monkeypatch):
    """Email confirmation is sent when notes contain near-trigger words."""
    contact = {
        "emailAddresses": [{"value": "bob@example.com"}],
        "names": [{"displayName": "Bob"}],
        "notes": "Firma ACME\nacme.com\nLet's do rserch soon\n+49 123456",
    }
    monkeypatch.setattr(google_contacts, "fetch_contacts", lambda: [contact])
    sent = {}
    monkeypatch.setattr(google_contacts.email_sender, "send", lambda **k: sent.update(k))
    logs = []
    monkeypatch.setattr(google_contacts, "log_step", lambda *a, **k: logs.append((a, k)))

    google_contacts.scheduled_poll()

    assert sent.get("to") == "bob@example.com"
    assert any(args[1] == "trigger_confirmation_pending" for args, _ in logs)
