"""Unit tests for the async ``app.core.orchestrator``."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.core.events import Event, EventUpdate
from app.core.orchestrator import HandlerResult, Orchestrator
from app.core.status import EventStatus


class InMemoryStore:
    """Simple in-memory event store for orchestrator tests."""

    def __init__(self, events: list[Event] | None = None) -> None:
        self._events: dict[str, Event] = {
            event.event_id: event for event in events or []
        }

    def list_pending(self, limit: int) -> list[Event]:
        pending = [
            event
            for event in self._events.values()
            if event.status is EventStatus.PENDING
        ]
        pending.sort(key=lambda event: event.created_at)
        return pending[:limit]

    def get(self, event_id: str) -> Event | None:
        return self._events.get(event_id)

    def update(self, event_id: str, patch: EventUpdate) -> Event:
        current = self._events[event_id]
        updated = replace(
            current,
            status=patch.status if patch.status is not None else current.status,
            payload=patch.payload if patch.payload is not None else current.payload,
            labels=list(patch.labels)
            if patch.labels is not None
            else list(current.labels),
            retries=patch.retries if patch.retries is not None else current.retries,
            last_error=patch.last_error
            if patch.last_error is not None
            else current.last_error,
            correlation_id=
            patch.correlation_id
            if patch.correlation_id is not None
            else current.correlation_id,
            updated_at=datetime.now(timezone.utc),
        )
        self._events[event_id] = updated
        return updated


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _event(event_id: str, *, status: EventStatus = EventStatus.PENDING) -> Event:
    now = datetime.now(timezone.utc)
    return Event(
        event_id=event_id,
        type="DemoEvent",
        created_at=now,
        updated_at=now,
        status=status,
        payload={"id": event_id},
    )


@pytest.mark.anyio("asyncio")
async def test_run_once_returns_zero_when_no_pending_events():
    store = InMemoryStore()
    orchestrator = Orchestrator(handlers={}, store=store)

    processed = await orchestrator.run_once()

    assert processed == 0


@pytest.mark.anyio("asyncio")
async def test_handler_success_marks_event_completed(monkeypatch):
    event = _event("evt-1")
    store = InMemoryStore([event])

    status_updates: list[tuple[str, EventStatus]] = []
    original_update = store.update

    def tracking_update(event_id: str, patch: EventUpdate) -> Event:
        updated = original_update(event_id, patch)
        status_updates.append((event_id, updated.status))
        return updated

    monkeypatch.setattr(store, "update", tracking_update)

    def handler(evt: Event) -> HandlerResult:
        assert evt.event_id == "evt-1"
        return HandlerResult(status=EventStatus.COMPLETED, payload={"processed": True})

    orchestrator = Orchestrator(handlers={"DemoEvent": handler}, store=store)

    processed = await orchestrator.run_once()

    assert processed == 1
    stored = store.get("evt-1")
    assert stored is not None
    assert stored.status is EventStatus.COMPLETED
    assert stored.payload["processed"] is True
    assert stored.last_error is None
    # status transitions: claim -> IN_PROGRESS, finalize -> COMPLETED
    assert any(status is EventStatus.IN_PROGRESS for _, status in status_updates)
    assert status_updates[-1][1] is EventStatus.COMPLETED


@pytest.mark.anyio("asyncio")
async def test_handler_failure_respects_retry_budget(monkeypatch):
    event = _event("evt-2")
    store = InMemoryStore([event])

    attempt_tracker = {"count": 0}

    def failing_handler(evt: Event):
        attempt_tracker["count"] += 1
        raise RuntimeError("boom")

    # avoid sleeping between retries
    orchestrator = Orchestrator(
        handlers={"DemoEvent": failing_handler},
        store=store,
        max_attempts=2,
        backoff=lambda attempt: 0,
    )

    processed = await orchestrator.run_once()

    assert processed == 1  # event fully processed despite failure
    stored = store.get("evt-2")
    assert stored is not None
    assert stored.status is EventStatus.FAILED
    assert stored.retries == 2
    assert "boom" in (stored.last_error or "")
    assert attempt_tracker["count"] == 2
