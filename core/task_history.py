from __future__ import annotations

"""Simple task history persistence layer using SQLite.

Records events related to tasks such as reminders or escalations. The
history shares the same SQLite database as :mod:`core.tasks`.
"""

from datetime import datetime, timezone
import sqlite3

from . import tasks

DB_PATH = tasks.DB_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS task_history (
               task_id TEXT NOT NULL,
               event TEXT NOT NULL,
               created_at TEXT NOT NULL
           )"""
    )
    return conn


def record_event(task_id: str, event: str) -> None:
    """Record a history ``event`` for ``task_id`` with the current timestamp."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO task_history VALUES (?, ?, ?)",
            (task_id, event, now),
        )
        conn.commit()


def has_event_since(task_id: str, event: str, since: datetime) -> bool:
    """Return ``True`` if ``task_id`` has ``event`` recorded since ``since``."""
    with _connect() as conn:
        cur = conn.execute(
            "SELECT 1 FROM task_history WHERE task_id = ? AND event = ? AND created_at >= ? LIMIT 1",
            (task_id, event, since.isoformat()),
        )
        return cur.fetchone() is not None


__all__ = ["record_event", "has_event_since"]
