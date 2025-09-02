from __future__ import annotations

import importlib
import os
from pathlib import Path

from integrations import email_sender


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

    log_path = Path("logs") / "workflows" / f"{event_id}.jsonl"
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
            "status": "needs_admin_fix",
            "error": str(error),
            "severity": "critical",
        }
    )
