import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:  # pragma: no cover - guard legacy orchestrator
    from core import orchestrator
except ImportError:  # pragma: no cover - orchestrator removed
    pytestmark = pytest.mark.skip(
        reason="Legacy orchestrator trigger detection removed; use app.core"
    )


def test_as_trigger_from_event_none_without_trigger():
    ev = {"summary": "Nothing here", "description": ""}
    assert orchestrator._as_trigger_from_event(ev) is None


def test_as_trigger_from_event_returns_payload_when_trigger_present():
    ev = {
        "summary": "Research meeting",
        "description": "",
        "creator": {"email": "alice@example.com"},
        "organizer": {"email": "bob@example.com"},
    }
    trig = orchestrator._as_trigger_from_event(ev)
    assert trig == {
        "source": "calendar",
        "creator": "alice@example.com",
        "recipient": "bob@example.com",
        "payload": ev,
    }


def test_as_trigger_from_event_detects_trigger_in_location():
    ev = {
        "summary": "Regular meeting",
        "description": "",
        "location": "Research campus",
        "creator": {"email": "alice@example.com"},
        "organizer": {"email": "bob@example.com"},
    }
    trig = orchestrator._as_trigger_from_event(ev)
    assert trig == {
        "source": "calendar",
        "creator": "alice@example.com",
        "recipient": "bob@example.com",
        "payload": ev,
    }


def test_as_trigger_from_event_detects_trigger_in_attendee():
    ev = {
        "summary": "Regular meeting",
        "description": "",
        "attendees": [{"email": "carol@meetingvorbereitung.com"}],
        "creator": {"email": "alice@example.com"},
        "organizer": {"email": "bob@example.com"},
    }
    trig = orchestrator._as_trigger_from_event(ev)
    assert trig == {
        "source": "calendar",
        "creator": "alice@example.com",
        "recipient": "bob@example.com",
        "payload": ev,
    }
