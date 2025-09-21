"""Unit tests covering the SQLite-backed event store helpers."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib
from contextlib import contextmanager

import pytest

from app.core.events import Event, EventUpdate
from app.core.status import EventStatus
from config.settings import SETTINGS


@pytest.fixture()
def fresh_store(tmp_path, monkeypatch):
    """Provide an isolated event_store module backed by a temp database."""

    db_path = tmp_path / "events.db"
    monkeypatch.setenv("TASKS_DB_PATH", str(db_path))
    monkeypatch.setattr(SETTINGS, "tasks_db_path", db_path, raising=False)
    monkeypatch.setattr(SETTINGS, "event_db_path", db_path, raising=False)
    monkeypatch.setattr(SETTINGS, "event_db_url", "", raising=False)
    monkeypatch.setattr(SETTINGS, "tasks_db_url", "", raising=False)

    from app.core import event_store as event_store_module

    store = importlib.reload(event_store_module)
    try:
        yield store
    finally:
        monkeypatch.delenv("TASKS_DB_PATH", raising=False)
        importlib.reload(event_store_module)


def _example_event(event_id: str = "EVT-001") -> Event:
    now = datetime.now(timezone.utc)
    return Event(
        event_id=event_id,
        type="UnitTestEvent",
        created_at=now,
        updated_at=now,
        status=EventStatus.PENDING,
        payload={"foo": "bar"},
        labels=["initial"],
        correlation_id="corr-1",
    )


def test_create_get_and_update_round_trip(fresh_store):
    store = fresh_store
    event = _example_event()

    store.create_event(event)

    retrieved = store.get(event.event_id)
    assert retrieved is not None
    assert retrieved.event_id == event.event_id
    assert retrieved.status is EventStatus.PENDING
    assert retrieved.payload == {"foo": "bar"}
    assert retrieved.labels == ["initial"]

    updated = store.update(
        event.event_id,
        EventUpdate(
            status=EventStatus.IN_PROGRESS,
            payload={"foo": "updated"},
            labels=["initial", "processing"],
        ),
    )

    assert updated.status is EventStatus.IN_PROGRESS
    assert updated.payload == {"foo": "updated"}
    assert updated.labels == ["initial", "processing"]
    assert updated.updated_at > retrieved.updated_at


def test_status_transitions_enforced(fresh_store):
    store = fresh_store
    event = _example_event("EVT-TRANS")
    store.create_event(event)

    in_progress = store.update(event.event_id, EventUpdate(status=EventStatus.IN_PROGRESS))
    assert in_progress.status is EventStatus.IN_PROGRESS

    waiting = store.update(event.event_id, EventUpdate(status=EventStatus.WAITING_USER))
    assert waiting.status is EventStatus.WAITING_USER

    with pytest.raises((store.InvalidStatusTransition, TypeError)):
        store.update(event.event_id, EventUpdate(status=EventStatus.COMPLETED))

    still_waiting = store.get(event.event_id)
    assert still_waiting is not None
    assert still_waiting.status is EventStatus.WAITING_USER


def test_optimistic_concurrency_detected(fresh_store, monkeypatch):
    store = fresh_store
    event = _example_event("EVT-CONFLICT")
    store.create_event(event)

    real_connect = store._connect

    def connect_with_conflict():
        @contextmanager
        def _context():
            with real_connect() as conn:
                conflicted = {"triggered": False}

                class ProxyConnection:
                    def __init__(self, inner):
                        self._inner = inner

                    def execute(self, sql, params=()):
                        cursor = self._inner.execute(sql, params)
                        if (
                            not conflicted["triggered"]
                            and sql.strip().upper().startswith("SELECT * FROM EVENTS WHERE EVENT_ID")
                        ):
                            conflicted["triggered"] = True
                            self._inner.execute(
                                "UPDATE events SET updated_at = ? WHERE event_id = ?",
                                (
                                    datetime.now(timezone.utc).isoformat(),
                                    params[0],
                                ),
                            )
                        return cursor

                    def __getattr__(self, name):
                        return getattr(self._inner, name)

                yield ProxyConnection(conn)

        return _context()

    monkeypatch.setattr(store, "_connect", connect_with_conflict)

    with pytest.raises(store.ConcurrencyError):
        store.update(event.event_id, EventUpdate(status=EventStatus.IN_PROGRESS))

    latest = store.get(event.event_id)
    assert latest is not None
    assert latest.status is EventStatus.PENDING

