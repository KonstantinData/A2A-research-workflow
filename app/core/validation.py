"""Validation helpers for orchestrator state transitions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from .status import EventStatus


_ALLOWED_TRANSITIONS: Mapping[EventStatus, frozenset[EventStatus]] = {
    EventStatus.PENDING: frozenset({EventStatus.IN_PROGRESS}),
    EventStatus.IN_PROGRESS: frozenset({
        EventStatus.COMPLETED,
        EventStatus.WAITING_USER,
        EventStatus.FAILED,
    }),
    EventStatus.WAITING_USER: frozenset({
        EventStatus.PENDING,
        EventStatus.IN_PROGRESS,
        EventStatus.FAILED,
    }),
    EventStatus.COMPLETED: frozenset(),
    EventStatus.FAILED: frozenset(),
    EventStatus.CANCELED: frozenset(),
}


@dataclass(slots=True)
class TransitionValidationError(ValueError):
    """Raised when a state transition violates lifecycle guards."""

    from_status: EventStatus
    to_status: EventStatus
    allowed: Tuple[EventStatus, ...]

    def __post_init__(self) -> None:
        message = (
            f"Illegal transition from {self.from_status.value!r} "
            f"to {self.to_status.value!r}; allowed: "
            f"{', '.join(status.value for status in self.allowed)}"
        )
        super().__init__(message)

    @property
    def details(self) -> dict[str, object]:
        """Structured error payload for logging or APIs."""

        return {
            "from": self.from_status.value,
            "to": self.to_status.value,
            "allowed": [status.value for status in self.allowed],
        }


def validate_transition(current: EventStatus, new: EventStatus) -> None:
    """Validate the transition from ``current`` to ``new``.

    Raises:
        TransitionValidationError: if the transition is not permitted by the
            lifecycle guards.
    """

    if new == current:
        return

    allowed: set[EventStatus] = set(_ALLOWED_TRANSITIONS.get(current, frozenset()))
    allowed.add(EventStatus.CANCELED)

    if new not in allowed:
        raise TransitionValidationError(
            current,
            new,
            tuple(sorted(allowed, key=lambda status: status.value)),
        )


def ensure_transition(current: EventStatus, new: EventStatus) -> None:
    """Backwards compatible wrapper for :func:`validate_transition`."""

    validate_transition(current, new)
