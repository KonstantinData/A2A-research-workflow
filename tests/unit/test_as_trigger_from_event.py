import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator


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
