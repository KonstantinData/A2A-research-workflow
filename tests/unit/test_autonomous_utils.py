from __future__ import annotations

from agents.autonomous_utils import ensure_trigger_structure


def test_ensure_trigger_structure_preserves_canonical_payload() -> None:
    event_payload = {
        "source": "calendar",
        "creator": "alice@example.com",
        "recipient": "bob@example.com",
        "payload": {"summary": "Call", "description": "Catch-up"},
    }

    trigger = ensure_trigger_structure(event_payload)

    assert trigger["creator"] == "alice@example.com"
    assert trigger["recipient"] == "bob@example.com"
    assert trigger["payload"] == {"summary": "Call", "description": "Catch-up"}
    assert "payload" not in trigger["payload"]


def test_ensure_trigger_structure_flattens_double_wrapped_payload() -> None:
    double_wrapped = {
        "payload": {
            "source": "calendar",
            "creator": "alice@example.com",
            "recipient": "bob@example.com",
            "payload": {"summary": "Call"},
        }
    }

    trigger = ensure_trigger_structure(double_wrapped)

    assert trigger["creator"] == "alice@example.com"
    assert trigger["recipient"] == "bob@example.com"
    assert trigger["payload"] == {"summary": "Call"}


def test_ensure_trigger_structure_wraps_raw_event_once() -> None:
    raw_event = {
        "source": "calendar",
        "creator": "alice@example.com",
        "summary": "Kick-off",
    }

    trigger = ensure_trigger_structure(raw_event)

    assert trigger["creator"] == "alice@example.com"
    assert trigger["payload"] == {"summary": "Kick-off"}
    assert "source" not in trigger["payload"]
