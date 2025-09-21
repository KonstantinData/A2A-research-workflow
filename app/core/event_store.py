"""SQLite-backed event store with optimistic concurrency control."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Optional
from dataclasses import replace
from datetime import datetime, timezone
from urllib.parse import urlparse

from config.settings import SETTINGS

from .events import Event, EventUpdate
from .status import EventStatus
from . import validation
from .schema import validate_event_payload


class EventStoreError(RuntimeError):
    """Base error for event store operations."""


class EventNotFoundError(EventStoreError):
    """Raised when an event could not be located."""


class ConcurrencyError(EventStoreError):
    """Raised when an update fails due to optimistic concurrency."""


class InvalidStatusTransition(EventStoreError):
    """Raised when an illegal status transition is attempted."""

    def __init__(
        self,
        current: EventStatus,
        new: EventStatus,
        allowed: Iterable[EventStatus],
    ) -> None:
        allowed_statuses = tuple(
            sorted({status for status in allowed}, key=lambda status: status.value)
        )
        self.current = current
        self.new = new
        self.allowed = allowed_statuses
        self.details = {
            "from": current.value,
            "to": new.value,
            "allowed": [status.value for status in allowed_statuses],
        }
        message = (
            f"Cannot transition event from {current.value} to {new.value}. "
            f"Allowed: {', '.join(self.details['allowed']) or '∅'}"
        )
        super().__init__(message)


def _default_db_path() -> Path:
    base = Path.cwd() / "data"
    events_path = base / "events.db"
    legacy_path = base / "tasks.db"
    if not events_path.exists() and legacy_path.exists():
        return legacy_path
    return events_path


def _path_from_url(url: str) -> Path:
    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme != "sqlite":
        raise ValueError(f"Unsupported database URL scheme: {parsed.scheme}")
    netloc = parsed.netloc or ""
    path = parsed.path or ""
    if netloc and not path.startswith("/"):
        path = f"/{path}"
    raw_path = f"{netloc}{path}" or path
    if not raw_path:
        return _default_db_path()
    return Path(raw_path)


def _resolve_db_path() -> Path:
    if SETTINGS.event_db_url:
        return _path_from_url(SETTINGS.event_db_url)
    if SETTINGS.tasks_db_url:
        return _path_from_url(SETTINGS.tasks_db_url)
    if SETTINGS.event_db_path:
        return SETTINGS.event_db_path
    if SETTINGS.tasks_db_path:
        return SETTINGS.tasks_db_path
    return _default_db_path()


_DB_PATH = _resolve_db_path()


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            payload TEXT,
            labels TEXT,
            correlation_id TEXT,
            retries INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_events_status
            ON events(status, updated_at DESC)
        """
    )
    return conn


def _serialize_payload(payload: Optional[dict]) -> str:
    return json.dumps(payload or {})


def _serialize_labels(labels: Optional[Iterable[str]]) -> str:
    return json.dumps(list(labels or []))


def _deserialize_payload(raw: Optional[str]) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EventStoreError("Stored payload is not valid JSON") from exc
    return value if isinstance(value, dict) else {}


def _deserialize_labels(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EventStoreError("Stored labels are not valid JSON") from exc
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _row_to_event(row: sqlite3.Row) -> Event:
    return Event(
        event_id=row["event_id"],
        type=row["type"],
        status=EventStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        payload=_deserialize_payload(row["payload"]),
        labels=_deserialize_labels(row["labels"]),
        correlation_id=row["correlation_id"],
        retries=row["retries"] or 0,
        last_error=row["last_error"],
    )


def _ensure_transition(current: EventStatus, new: EventStatus) -> None:
    if new == current:
        return
    try:
        validation.ensure_transition(current, new)
    except validation.TransitionValidationError as exc:  # pragma: no cover - defensive
        raise InvalidStatusTransition(exc.from_status, exc.to_status, exc.allowed) from exc


def create_event(event: Event) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO events (
                event_id, type, status, created_at, updated_at, payload,
                labels, correlation_id, retries, last_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.type,
                event.status.value,
                event.created_at.isoformat(),
                event.updated_at.isoformat(),
                _serialize_payload(event.payload),
                _serialize_labels(event.labels),
                event.correlation_id,
                event.retries,
                event.last_error,
            ),
        )


def get(event_id: str) -> Optional[Event]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
    if not row:
        return None
    return _row_to_event(row)


def update(event_id: str, patch: EventUpdate) -> Event:
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if not row:
            raise EventNotFoundError(f"Event {event_id} not found")
        current = _row_to_event(row)

        if patch.payload is not None:
            validate_event_payload(current.type, patch.payload)

        new_status = patch.status or current.status
        _ensure_transition(current.status, new_status)

        new_payload = patch.payload if patch.payload is not None else current.payload
        new_labels = patch.labels if patch.labels is not None else current.labels
        new_retries = patch.retries if patch.retries is not None else current.retries
        new_last_error = patch.last_error if patch.last_error is not None else current.last_error
        new_correlation_id = (
            patch.correlation_id
            if patch.correlation_id is not None
            else current.correlation_id
        )
        updated_at = datetime.now(timezone.utc)

        cursor = conn.execute(
            """
            UPDATE events
               SET status = ?,
                   payload = ?,
                   labels = ?,
                   retries = ?,
                   last_error = ?,
                   correlation_id = ?,
                   updated_at = ?
             WHERE event_id = ? AND updated_at = ?
            """,
            (
                new_status.value,
                _serialize_payload(new_payload),
                _serialize_labels(new_labels),
                new_retries,
                new_last_error,
                new_correlation_id,
                updated_at.isoformat(),
                event_id,
                current.updated_at.isoformat(),
            ),
        )
        if cursor.rowcount == 0:
            raise ConcurrencyError(f"Event {event_id} was updated concurrently")
        return replace(
            current,
            status=new_status,
            payload=new_payload,
            labels=list(new_labels),
            retries=new_retries,
            last_error=new_last_error,
            correlation_id=new_correlation_id,
            updated_at=updated_at,
        )


def list_by_status(status: EventStatus, limit: int) -> list[Event]:
    if limit <= 0:
        return []
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM events
             WHERE status = ?
             ORDER BY updated_at DESC
             LIMIT ?
            """,
            (status.value, limit),
        ).fetchall()
    return [_row_to_event(row) for row in rows]


def list_pending(limit: int) -> list[Event]:
    return list_by_status(EventStatus.PENDING, limit)


def list_events(
    *,
    limit: int = 50,
    offset: int = 0,
    correlation_id: Optional[str] = None,
) -> list[Event]:
    limit = max(0, int(limit))
    offset = max(0, int(offset))
    query = "SELECT * FROM events"
    params: list[Any] = []
    if correlation_id:
        query += " WHERE correlation_id = ?"
        params.append(correlation_id)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_event(row) for row in rows]


class EventStore:
    """Thin façade over the module-level store helpers.

    The orchestrator interacts with an ``EventStore`` instance so unit tests can
    supply lightweight fakes while production code continues to use the SQLite
    helpers defined in this module.
    """

    @staticmethod
    def create_event(event: Event) -> None:
        create_event(event)

    @staticmethod
    def list_pending(limit: int) -> list[Event]:
        return list_pending(limit)

    @staticmethod
    def list_events(
        *, limit: int = 50, offset: int = 0, correlation_id: Optional[str] = None
    ) -> list[Event]:
        return list_events(limit=limit, offset=offset, correlation_id=correlation_id)

    @staticmethod
    def get(event_id: str) -> Optional[Event]:
        return get(event_id)

    @staticmethod
    def update(event_id: str, patch: EventUpdate) -> Event:
        return update(event_id, patch)


def upsert_label(event_id: str, label: str) -> None:
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT labels, updated_at FROM events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if not row:
            raise EventNotFoundError(f"Event {event_id} not found")

        labels = _deserialize_labels(row["labels"])
        if label in labels:
            return
        labels.append(label)
        updated_at = datetime.now(timezone.utc)

        cursor = conn.execute(
            """
            UPDATE events
               SET labels = ?,
                   updated_at = ?
             WHERE event_id = ? AND updated_at = ?
            """,
            (
                _serialize_labels(labels),
                updated_at.isoformat(),
                event_id,
                row["updated_at"],
            ),
        )
        if cursor.rowcount == 0:
            raise ConcurrencyError(f"Event {event_id} was updated concurrently")

