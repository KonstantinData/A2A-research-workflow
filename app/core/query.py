"""Convenience helpers for querying the event store."""

from __future__ import annotations

from typing import List

from .event_store import EventNotFoundError, EventStore, upsert_label
from .status import EventStatus


def _get_event(event_id: str):
    event = EventStore.get(event_id)
    if event is None:
        raise EventNotFoundError(f"Event {event_id} not found")
    return event


def get_status(event_id: str) -> EventStatus:
    """Return the persisted status for ``event_id``."""

    return _get_event(event_id).status


def get_labels(event_id: str) -> List[str]:
    """Return the labels currently associated with ``event_id``."""

    return list(_get_event(event_id).labels)


def add_label(event_id: str, label: str) -> None:
    """Attach ``label`` to ``event_id`` if it is not already present."""

    upsert_label(event_id, label)


__all__ = ["add_label", "get_labels", "get_status"]
