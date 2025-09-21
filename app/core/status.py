"""Event status definitions and helpers."""
from __future__ import annotations

from enum import Enum


class EventStatus(str, Enum):
    """Enumerates the lifecycle states for an event."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


_TERMINAL_STATUSES = {
    EventStatus.COMPLETED,
    EventStatus.FAILED,
    EventStatus.CANCELED,
}


def is_terminal(status: EventStatus) -> bool:
    """Return ``True`` when an event is in a terminal state."""

    return status in _TERMINAL_STATUSES
