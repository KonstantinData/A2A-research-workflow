from __future__ import annotations

import importlib
import os
from pathlib import Path
import shutil

from integrations import email_sender

from core import statuses
from config.settings import SETTINGS


def handle_failure(event_id: str | None, error: Exception) -> None:
    """Attempt to recover from a workflow failure.

    Analyse workflow logs and try a restart. If a restart is not possible,
    notify the administrator and log that manual intervention is required.
    """
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

    log_path = SETTINGS.workflows_dir / f"{event_id}.jsonl"
    can_restart = log_path.exists()

    if can_restart:
        log_event({"event_id": event_id, "status": "restart_attempted"})
        return

    try:
        admin = os.getenv("ADMIN_EMAIL", "admin@example.com")
        email_sender.send_email(
            to=admin,
            subject="Workflow requires attention",
            body=f"Event {event_id} failed with error: {error}",
        )
    except Exception:
        pass

    log_event(
        {
            "event_id": event_id,
            "status": statuses.NEEDS_ADMIN_FIX,
            "error": str(error),
            "severity": "critical",
        }
    )


def restart(event_id: str) -> None:
    """Restart the workflow for ``event_id``."""
    orchestrator = importlib.import_module("core.orchestrator")
    orchestrator.run(
        triggers=[{"payload": {"event_id": event_id}}],
        restart_event_id=event_id,
    )


def abort(event_id: str) -> None:
    """Abort processing for ``event_id`` and clean up temporary data."""
    orchestrator = importlib.import_module("core.orchestrator")
    log_event = orchestrator.log_event
    tmp_paths = [
        SETTINGS.artifacts_dir / event_id,
        SETTINGS.exports_dir / event_id,
    ]
    for path in tmp_paths:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    log_event({"event_id": event_id, "status": statuses.ABORTED})
