from __future__ import annotations

import importlib
import json
import os
import shutil

from integrations import email_sender

from core import statuses
from config.settings import SETTINGS


def handle_failure(event_id: str | None, error: Exception) -> None:
    """Attempt to recover from a workflow failure.

    Analyse workflow logs and try a restart. If a restart is not possible,
    notify the administrator and log that manual intervention is required.
    """
    if not event_id:
        return
        
    orchestrator = importlib.import_module("core.orchestrator")
    log_event = orchestrator.log_event

    log_event(
        {
            "event_id": event_id,
            "status": "recovery_attempt",
            "error": str(error),
            "severity": "error",
        }
    )

    try:
        workflows_dir = SETTINGS.workflows_dir
        latest_status = None
        entry_found = False

        if workflows_dir.exists():
            for path in sorted(workflows_dir.glob("*.jsonl")):
                try:
                    with path.open("r", encoding="utf-8") as fh:
                        for line in fh:
                            try:
                                record = json.loads(line)
                            except Exception:
                                continue
                            if record.get("event_id") != event_id:
                                continue
                            entry_found = True
                            status = record.get("status")
                            if status and status != "fetched":
                                latest_status = status
                except Exception:
                    continue

        terminal_statuses = statuses.FINAL_STATUSES | statuses.PAUSE_STATUSES

        if entry_found and latest_status not in terminal_statuses:
            log_event({"event_id": event_id, "status": "restart_attempted"})
            return

        try:
            admin = os.getenv("ADMIN_EMAIL", "admin@example.com")
            email_sender.send_email(
                to=admin,
                subject="Workflow requires attention",
                body=f"Event {event_id} failed with error: {error}",
            )
        except Exception as email_error:
            log_event(
                {
                    "event_id": event_id,
                    "status": "email_notification_failed",
                    "error": str(email_error),
                    "severity": "error",
                }
            )

        log_event(
            {
                "event_id": event_id,
                "status": statuses.NEEDS_ADMIN_FIX,
                "error": str(error),
                "severity": "critical",
            }
        )
    except Exception as recovery_error:
        log_event(
            {
                "event_id": event_id,
                "status": "recovery_failed",
                "error": str(recovery_error),
                "severity": "critical",
            }
        )


def restart(event_id: str) -> None:
    """Restart the workflow for ``event_id``."""
    if not event_id:
        raise ValueError("event_id is required")
        
    try:
        orchestrator = importlib.import_module("core.orchestrator")
        log_event = orchestrator.log_event
        
        log_event({"event_id": event_id, "status": "restart_initiated"})
        
        orchestrator.run(
            triggers=[{"payload": {"event_id": event_id}}],
            restart_event_id=event_id,
        )
    except Exception as restart_error:
        orchestrator = importlib.import_module("core.orchestrator")
        log_event = orchestrator.log_event
        log_event(
            {
                "event_id": event_id,
                "status": "restart_failed",
                "error": str(restart_error),
                "severity": "critical",
            }
        )
        raise


def abort(event_id: str) -> None:
    """Abort processing for ``event_id`` and clean up temporary data."""
    if not event_id:
        raise ValueError("event_id is required")
        
    orchestrator = importlib.import_module("core.orchestrator")
    log_event = orchestrator.log_event
    
    log_event({"event_id": event_id, "status": "abort_initiated"})
    
    tmp_paths = [
        SETTINGS.artifacts_dir / event_id,
        SETTINGS.exports_dir / event_id,
    ]
    
    cleanup_errors = []
    for path in tmp_paths:
        try:
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        except Exception as cleanup_error:
            cleanup_errors.append(f"{path}: {cleanup_error}")
    
    if cleanup_errors:
        log_event(
            {
                "event_id": event_id,
                "status": "cleanup_partial_failure",
                "error": "; ".join(cleanup_errors),
                "severity": "error",
            }
        )
    
    log_event({"event_id": event_id, "status": statuses.ABORTED})
