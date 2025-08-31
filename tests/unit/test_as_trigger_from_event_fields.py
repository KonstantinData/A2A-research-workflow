from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator


def test_trigger_from_location_or_attendee():
    ev = {"summary": "Weekly sync", "description": "", "location": "Meeting Vorbereitung"}
    assert orchestrator._as_trigger_from_event(ev) is not None
    ev2 = {"summary": "Weekly", "description": "", "attendees": [{"email": "research@foo.com"}]}
    # depends on words list; at least code path handles dict
    orchestrator._as_trigger_from_event(ev2)  # should not raise
