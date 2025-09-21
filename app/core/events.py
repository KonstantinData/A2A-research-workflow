"""Event domain models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .status import EventStatus


@dataclass(slots=True)
class Event:
    """Represents an event emitted within the system."""

    event_id: str
    type: str
    created_at: datetime
    updated_at: datetime
    status: EventStatus
    payload: Dict[str, Any]
    labels: List[str] = field(default_factory=list)
    correlation_id: Optional[str] = None
    retries: int = 0
    last_error: Optional[str] = None


@dataclass(slots=True)
class EventUpdate:
    """Mutable fields that can be updated on an event."""

    status: Optional[EventStatus] = None
    payload: Optional[Dict[str, Any]] = None
    labels: Optional[List[str]] = None
    retries: Optional[int] = None
    last_error: Optional[str] = None
    correlation_id: Optional[str] = None
