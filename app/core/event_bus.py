"""Event bus integration that persists events to the event store."""

from __future__ import annotations

import asyncio
import inspect
import uuid
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from typing import Awaitable, Callable, DefaultDict, List, Optional

from core.utils import log_step

from .event_store import EventStore, EventStoreError
from .events import Event
from .status import EventStatus


Subscriber = Callable[[Event], Awaitable[None] | None]


def _generate_event_id() -> str:
    """Generate a unique identifier that is safe for e-mail subjects."""

    return str(uuid.uuid4()).upper()


class EventBus:
    """Simple event bus that persists every published event."""

    def __init__(self, *, store: Optional[EventStore] = None) -> None:
        self._store = store or EventStore()
        self._subscribers: DefaultDict[str, List[Subscriber]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Subscriber) -> None:
        """Register *handler* for ``event_type``."""

        self._subscribers[event_type].append(handler)

    def publish(self, event: Event) -> Event:
        """Persist *event* and synchronously notify subscribers."""

        now = datetime.now(timezone.utc)
        event_id = event.event_id or _generate_event_id()
        persisted = replace(
            event,
            event_id=event_id,
            status=EventStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

        try:
            self._store.create_event(persisted)
        except EventStoreError as exc:
            log_step(
                "event_bus",
                "persist_failed",
                {"event_id": event_id, "type": persisted.type, "error": str(exc)},
                severity="error",
            )
            raise

        log_step(
            "event_bus",
            "event_published",
            {"event_id": event_id, "type": persisted.type},
        )

        self._deliver(persisted)
        return persisted

    def _deliver(self, event: Event) -> None:
        """Dispatch *event* to registered subscribers."""

        for handler in list(self._subscribers.get(event.type, [])):
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    self._schedule(result)
            except Exception as exc:  # pragma: no cover - defensive
                log_step(
                    "event_bus",
                    "handler_failed",
                    {"event_id": event.event_id, "type": event.type, "error": str(exc)},
                    severity="error",
                )

    @staticmethod
    def _schedule(awaitable: Awaitable[object]) -> None:
        """Execute *awaitable* either on the running loop or a temporary one."""

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(awaitable)
            return
        loop.create_task(awaitable)


__all__ = ["EventBus"]
