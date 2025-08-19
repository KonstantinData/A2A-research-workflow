"""Tests for the orchestrator module."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator


def test_gather_triggers_normalizes_data():
    events = [{"creator": "alice@example.com", "summary": "Test"}]
    contacts = [
        {"emailAddresses": [{"value": "bob@example.com"}], "names": []}
    ]

    triggers = orchestrator.gather_triggers(lambda: events, lambda: contacts)

    assert triggers == [
        {
            "source": "calendar",
            "creator": "alice@example.com",
            "recipient": "alice@example.com",
            "payload": events[0],
        },
        {
            "source": "contacts",
            "creator": "bob@example.com",
            "recipient": "bob@example.com",
            "payload": contacts[0],
        },
    ]


def test_run_sends_email(monkeypatch):
    events = [{"creator": "carol@example.com"}]
    contacts = []
    sent = []

    def fake_send(to, subject, body, attachments=None):  # pragma: no cover - simple stub
        sent.append((to, subject, body))

    orchestrator.run(lambda: events, lambda: contacts, send=fake_send)

    assert sent == [
        (
            "carol@example.com",
            "Research workflow triggered",
            "Trigger source: calendar",
        )
    ]

