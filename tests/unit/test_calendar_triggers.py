from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.triggers import _as_trigger_from_event, gather_calendar_triggers
from integrations import google_calendar


def test_gather_calendar_triggers_accepts_payload_id():
    events: List[Dict[str, Any]] = [
        {"payload": {"id": "abc", "summary": "besuchsvorbereitung"}}
    ]
    logged_events: List[Dict[str, Any]] = []
    logged_steps: List[Tuple[str, str, Dict[str, Any]]] = []

    def fake_log_event(entry: Dict[str, Any]) -> None:
        logged_events.append(entry)

    def fake_log_step(source: str, name: str, payload: Dict[str, Any]) -> None:
        logged_steps.append((source, name, payload))

    triggers = gather_calendar_triggers(
        events=events,
        contains_trigger=lambda payload: True,
        log_event=fake_log_event,
        log_step=fake_log_step,
        get_workflow_id=lambda: "wf-test",
    )

    assert len(triggers) == 1
    assert triggers[0]["payload"]["id"] == "abc"
    assert triggers[0]["payload"]["summary"] == "besuchsvorbereitung"
    assert not any(step[1] == "event_discarded" for step in logged_steps)
    assert not any(event.get("status") == "no_calendar_events" for event in logged_events)


def test_normalized_event_keeps_recipient():
    raw_event = {
        "id": "evt-1",
        "summary": "Besuchsvorbereitung call",
        "creator": {"email": "alice@example.com"},
        "organizer": {"email": "bob@example.com"},
    }

    normalized = google_calendar._normalize(raw_event, "primary")
    event = dict(normalized)
    event["payload"] = dict(normalized)

    trigger = _as_trigger_from_event(event, contains_trigger=lambda payload: True)

    assert trigger is not None
    assert trigger["recipient"] == "bob@example.com"
