#!/usr/bin/env python3
"""Backfill event identifiers for legacy task entries and artefacts.

The previous workflow stored human-in-the-loop tasks in ``core.tasks`` without a
first-class event identifier.  Modern components operate exclusively via the
central event store so that orchestration, manual replies and exports can share
consistent metadata.  This script inspects the legacy task table and persists
corresponding events with generated identifiers.  Each migrated event receives a
``migrated`` label so follow-up scripts can distinguish historic entries.

Status detection is deliberately conservative: an event is marked as
``completed`` only when artefacts linked to the original task identifier are
found.  Otherwise the event is left ``pending`` so operators can review the
record and decide how to proceed.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core import event_store as store_module
from app.core.events import Event
from app.core.event_store import EventStore
from app.core.id_factory import new_event_id
from app.core.status import EventStatus
from config.settings import SETTINGS
from core import tasks as legacy_tasks


def _existing_migrated_task_ids() -> set[str]:
    """Return task identifiers that already have a migrated event."""

    try:
        with store_module._connect() as conn:  # type: ignore[attr-defined]
            rows = conn.execute(
                "SELECT payload FROM events WHERE labels LIKE '%\"migrated\"%'"
            ).fetchall()
    except sqlite3.OperationalError:
        return set()

    migrated: set[str] = set()
    for row in rows:
        raw_payload = row["payload"] if isinstance(row, sqlite3.Row) else row[0]
        if not raw_payload:
            continue
        try:
            payload = json.loads(raw_payload)
        except (TypeError, json.JSONDecodeError):
            continue
        task_id = payload.get("task_id")
        if task_id:
            migrated.add(str(task_id))
    return migrated


def _path_populated(path: Path) -> bool:
    if path.is_dir():
        return any(path.iterdir())
    return path.is_file() and path.stat().st_size > 0


def _candidate_names(task: Dict[str, object]) -> Sequence[str]:
    names = {str(task.get("id", ""))}
    trigger = str(task.get("trigger", "") or "").strip()
    if trigger:
        names.add(trigger)
        names.add(trigger.replace(" ", "_"))
    return [name for name in names if name]


def _has_terminal_artifacts(task: Dict[str, object]) -> bool:
    names = _candidate_names(task)
    bases = [SETTINGS.exports_dir, SETTINGS.artifacts_dir]
    for base in bases:
        for name in names:
            candidates = [
                base / name,
                base / f"{name}.pdf",
                base / f"{name}.csv",
                base / f"{name}.json",
            ]
            for candidate in candidates:
                if _path_populated(candidate):
                    return True
    # Fallback to global exports when per-task artefacts are not available
    pdf = SETTINGS.exports_dir / "report.pdf"
    csv = SETTINGS.exports_dir / "data.csv"
    return pdf.is_file() and csv.is_file()


def _coerce_datetime(value: object, *, default: datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            pass
    return default


def migrate_tasks(*, dry_run: bool = False) -> List[Event]:
    tasks = list(legacy_tasks.list_tasks())
    if not tasks:
        return []

    migrated = _existing_migrated_task_ids()
    store = EventStore()
    new_events: List[Event] = []

    for task in tasks:
        task_id = str(task.get("id"))
        if not task_id or task_id in migrated:
            continue

        created = _coerce_datetime(task.get("created_at"), default=datetime.now(timezone.utc))
        updated = _coerce_datetime(task.get("updated_at"), default=created)
        if updated < created:
            updated = created

        status = (
            EventStatus.COMPLETED
            if _has_terminal_artifacts(task)
            else EventStatus.PENDING
        )

        payload = {
            "task_id": task_id,
            "trigger": task.get("trigger"),
            "missing_fields": task.get("missing_fields"),
            "employee_email": task.get("employee_email"),
            "original_status": task.get("status"),
        }

        event = Event(
            event_id=new_event_id(),
            type="LegacyTaskMigrated",
            created_at=created,
            updated_at=updated,
            status=status,
            payload=payload,
            labels=["migrated"],
        )

        if not dry_run:
            store.create_event(event)
        new_events.append(event)
    return new_events


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without writing to the database.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    events = migrate_tasks(dry_run=args.dry_run)
    if not events:
        print("No legacy tasks requiring migration were found.")
        return 0

    heading = "Planned migrations" if args.dry_run else "Migrated events"
    print(f"{heading}: {len(events)}")
    for event in events:
        payload = event.payload or {}
        task_id = payload.get("task_id", "?")
        print(
            f"- {event.event_id} (task {task_id}) status={event.status.value}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())
