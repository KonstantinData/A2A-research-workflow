from __future__ import annotations

"""Simple task persistence layer using SQLite.

This module defines a ``Task`` dataclass and CRUD helpers to create, read,
update and delete task records. Records persist on disk via SQLite so they
survive process restarts.  Historically the configuration used a
``TASKS_DB_PATH`` environment variable but parts of the codebase (and the
tests in this kata) expect a ``TASKS_DB_URL`` style variable.  To remain
compatible with both we honour ``TASKS_DB_URL`` when present and fall back to
``TASKS_DB_PATH`` otherwise.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import logging

from config.settings import SETTINGS

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
# Determine database location.  ``TASKS_DB_URL`` is expected to contain a
# ``sqlite:///`` style URL while ``TASKS_DB_PATH`` points directly to a file.  We
# normalise both to a simple ``Path`` for ``sqlite3``.
DEFAULT_DB_PATH = SETTINGS.root_dir / "data" / "tasks.db"
if SETTINGS.tasks_db_url:
    DB_PATH = Path(SETTINGS.tasks_db_url.replace('sqlite:///', '', 1))
elif SETTINGS.tasks_db_path:
    DB_PATH = SETTINGS.tasks_db_path
else:
    DB_PATH = DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def _log_action(action: str, task: Dict[str, Any]) -> None:
    payload = {
        "action": action,
        "task_id": task.get("id"),
        "status": task.get("status"),
        "assigned_to": task.get("employee_email"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(json.dumps(payload))


def _connect() -> sqlite3.Connection:
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS tasks (
                   id TEXT PRIMARY KEY,
                   trigger TEXT NOT NULL,
                   missing_fields TEXT NOT NULL,
                   employee_email TEXT NOT NULL,
                   status TEXT NOT NULL,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL
               )'''
        )
        return conn
    except (sqlite3.Error, OSError) as e:
        logger.error("Database connection failed: %s", e)
        raise RuntimeError(f"Failed to connect to database: {e}") from e


# ---------------------------------------------------------------------------
# Dataclass model
# ---------------------------------------------------------------------------
@dataclass
class Task:
    id: str
    trigger: str
    missing_fields: Any
    employee_email: str
    status: str
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['missing_fields'] = self.missing_fields
        return d


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------
def create_task(
    trigger: str,
    missing_fields: Any,
    employee_email: str,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    task = Task(
        id=str(uuid.uuid4()),
        trigger=trigger,
        missing_fields=missing_fields,
        employee_email=employee_email,
        status='pending',
        created_at=now,
        updated_at=now,
    )
    with _connect() as conn:
        conn.execute(
            'INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)',
            (
                task.id,
                task.trigger,
                json.dumps(task.missing_fields),
                task.employee_email,
                task.status,
                task.created_at.isoformat(),
                task.updated_at.isoformat(),
            ),
        )
        conn.commit()
    record = task.to_dict()
    _log_action("create", record)
    return record


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        row = cur.fetchone()
        if not row:
            return None
        try:
            missing_fields = json.loads(row['missing_fields'])
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Invalid JSON in missing_fields for task %s: %s", row['id'], e)
            missing_fields = []
        task = {
            'id': row['id'],
            'trigger': row['trigger'],
            'missing_fields': missing_fields,
            'employee_email': row['employee_email'],
            'status': row['status'],
            'created_at': datetime.fromisoformat(row['created_at']),
            'updated_at': datetime.fromisoformat(row['updated_at']),
        }
        _log_action("read", task)
        return task


def update_task_status(task_id: str, status: str) -> Optional[Dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            'UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?',
            (status, now, task_id),
        )
        conn.commit()
        cur = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        row = cur.fetchone()
    if not row:
        return None
    try:
        missing_fields = json.loads(row['missing_fields'])
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("Invalid JSON in missing_fields for task %s: %s", row['id'], e)
        missing_fields = []
    task = {
        'id': row['id'],
        'trigger': row['trigger'],
        'missing_fields': missing_fields,
        'employee_email': row['employee_email'],
        'status': row['status'],
        'created_at': datetime.fromisoformat(row['created_at']),
        'updated_at': datetime.fromisoformat(row['updated_at']),
    }
    _log_action("update", task)
    return task


def delete_task(task_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        deleted = cur.rowcount > 0
    if deleted:
        _log_action("delete", {"id": task_id, "status": "deleted", "employee_email": None})
    return deleted


def list_tasks() -> Iterable[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute('SELECT * FROM tasks')
        rows = cur.fetchall()
        return [
            {
                'id': r['id'],
                'trigger': r['trigger'],
                'missing_fields': json.loads(r['missing_fields']),
                'employee_email': r['employee_email'],
                'status': r['status'],
                'created_at': datetime.fromisoformat(r['created_at']),
                'updated_at': datetime.fromisoformat(r['updated_at']),
            }
            for r in rows
        ]


def pending_tasks() -> Iterable[Dict[str, Any]]:
    """Return tasks awaiting an e-mail reply."""
    return [
        t for t in list_tasks() if t.get("status") in {"pending", "reminded"}
    ]


__all__ = [
    'create_task',
    'get_task',
    'update_task_status',
    'delete_task',
    'list_tasks',
    'pending_tasks',
    'Task',
]
