"""Utility helpers for autonomous agents."""
from __future__ import annotations

from typing import Any, Dict


_METADATA_KEYS = {
    "source",
    "workflow_id",
    "trigger_id",
    "correlation_id",
}


def ensure_trigger_structure(event_payload: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return a trigger dict with a single level of payload nesting.

    Legacy agents expect triggers with top-level metadata (source, creator,
    recipient, etc.) and the normalized event stored under the ``payload`` key.
    When autonomous events already follow that schema we simply clone the
    structure.  If they are passed a raw normalized event (without the wrapper),
    we wrap it once while keeping any metadata fields that may have been
    provided alongside it.
    """
    if not isinstance(event_payload, dict):
        return {"payload": {}}

    nested_payload = event_payload.get("payload")
    if isinstance(nested_payload, dict):
        if isinstance(nested_payload.get("payload"), dict):
            normalized = ensure_trigger_structure(nested_payload)
            trigger = {k: v for k, v in normalized.items() if k != "payload"}
            trigger["payload"] = normalized["payload"]
            return trigger

        trigger = {k: v for k, v in event_payload.items() if k != "payload"}
        trigger["payload"] = dict(nested_payload)
        return trigger

    normalized_payload = dict(event_payload)
    trigger: Dict[str, Any] = {"payload": normalized_payload}

    for key in _METADATA_KEYS:
        if key in event_payload:
            trigger[key] = event_payload[key]
            # Avoid duplicating metadata inside the nested payload copy
            normalized_payload.pop(key, None)

    for key in ("creator", "recipient", "creator_name", "recipient_name"):
        if key in event_payload:
            value = event_payload[key]
            trigger[key] = value
            if not isinstance(value, dict):
                normalized_payload.pop(key, None)

    return trigger
