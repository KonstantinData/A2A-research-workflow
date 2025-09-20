"""Reminder scheduling service."""

from __future__ import annotations

import time
from datetime import datetime, time as dtime, timedelta, timezone

import importlib.util as _ilu
from pathlib import Path

import json
import logging

from core import tasks, statuses as status_defs
# task_history removed - using event bus for history
from core.utils import get_workflow_id
from integrations import email_client, email_sender
from agents.templates import build_reminder_email
from config.settings import SETTINGS

# JSONL logging for reminder notifications
_JSONL_PATH = Path(__file__).resolve().parents[1] / "a2a_logging" / "jsonl_sink.py"
_spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]
append_jsonl = _mod.append


def _reminder_log_path() -> Path:
    return SETTINGS.workflows_dir / "reminders.jsonl"


logger = logging.getLogger(__name__)


def log_event(record: dict) -> None:
    """Write ``record`` to a workflow JSONL log with a common schema."""
    wf_id = get_workflow_id()
    path = SETTINGS.workflows_dir / f"{wf_id}.jsonl"
    payload = {
        "event_id": record.get("event_id"),
        "status": record.get("status"),
        "timestamp": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "severity": record.get("severity", "info"),
        "workflow_id": wf_id,
        "details": {},
    }
    for k, v in record.items():
        if k not in {"event_id", "status", "timestamp", "severity", "workflow_id", "details"}:
            payload["details"][k] = v
        elif k == "details" and isinstance(v, dict):
            payload["details"].update(v)
    SETTINGS.workflows_dir.mkdir(parents=True, exist_ok=True)
    append_jsonl(path, payload)


def task_age_in_days(task: dict) -> int:
    """Return age of ``task`` in whole days."""
    created = task.get("created_at")
    if isinstance(created, str):
        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            return 0
    elif isinstance(created, datetime):
        created_dt = created
    else:
        return 0
    return (datetime.now(timezone.utc) - created_dt).days


def maybe_send_reminder(task: dict) -> None:
    if task.get("status") != "awaiting employee response":
        return
    
    # Validate required fields before accessing them
    missing_fields = task.get("missing_fields")
    employee_email = task.get("employee_email")
    
    if not missing_fields or not employee_email:
        return
    
    days = task_age_in_days(task)
    if days == 2:
        email_sender.send_missing_fields_reminder(
            task, missing_fields, employee_email, final=False
        )
    elif days == 6:
        email_sender.send_missing_fields_reminder(
            task, missing_fields, employee_email, final=True
        )


class ReminderScheduler:
    """Send daily reminder e-mails for open tasks at 10:00 and escalate at 15:00."""

    @staticmethod
    def _open_tasks():
        """Return tasks that are still pending or awaiting escalation."""
        return list(tasks.pending_tasks())

    def send_reminders(self) -> None:
        """Send reminder e-mails for all open tasks and record history."""
        logger.info("send_reminders job started")
        processed = 0
        try:
            for task in self._open_tasks():
                # Validate required task fields
                if not all(key in task for key in ["employee_email", "missing_fields", "id", "trigger"]):
                    logger.warning("Skipping task with missing fields: %s", task.get("id", "unknown"))
                    continue
                    
                email_client.send_email(
                    task["employee_email"], task["missing_fields"], task_id=task["id"]
                )
                # task_history.record_event(task["id"], "reminder_sent")  # Using event bus now
                tasks.update_task_status(task["id"], "reminded")
                log_event({"event_id": task["trigger"], "status": "reminder_sent", "task_id": task["id"]})
                processed += 1
            logger.info(
                "send_reminders job finished",
                extra={"tasks_processed": processed},
            )
        except Exception:
            logger.error("send_reminders job failed", exc_info=True)
            raise

    def escalate_tasks(self) -> None:
        """Send escalation e-mails for tasks without response after reminder."""
        logger.info("escalate_tasks job started")
        processed = 0
        try:
            today_start = datetime.combine(self._now().date(), dtime.min)
            for task in self._open_tasks():
                # Skip task_history checks - using event bus now
                # if not task_history.has_event_since(task["id"], "reminder_sent", today_start):
                #     continue
                # if task_history.has_event_since(task["id"], "escalated", today_start):
                #     continue
                subject = f"Escalation: no response for task {task['id']}"
                body = "No response was received for the reminder sent at 10:00."
                email_sender.send_email(
                    to="admin@condata.io",
                    subject=subject,
                    body=body,
                    task_id=task["id"],
                )
                # task_history.record_event(task["id"], "escalated")  # Using event bus now
                tasks.update_task_status(task["id"], "escalated")
                log_event({"event_id": task["trigger"], "status": "escalation_sent", "task_id": task["id"]})
                processed += 1
            logger.info(
                "escalate_tasks job finished",
                extra={"tasks_processed": processed},
            )
        except Exception:
            logger.error("escalate_tasks job failed", exc_info=True)
            raise

    def run_forever(self) -> None:
        """Run the scheduler loop indefinitely."""
        while True:
            now = self._now()
            reminder_at = datetime.combine(now.date(), dtime(hour=10, minute=0))
            escalation_at = datetime.combine(now.date(), dtime(hour=15, minute=0))

            if now < reminder_at:
                next_run = reminder_at
                action = self.send_reminders
            elif now < escalation_at:
                next_run = escalation_at
                action = self.escalate_tasks
            else:
                next_run = reminder_at + timedelta(days=1)
                action = self.send_reminders

            self._sleep((next_run - now).total_seconds())
            action()

    def _now(self) -> datetime:
        """Return current datetime, extracted for ease of testing."""
        return datetime.now(timezone.utc)

    def _sleep(self, seconds: float) -> None:
        """Sleep for a number of seconds, isolated for testing."""
        time.sleep(seconds)


def check_and_notify(triggers: list[dict]) -> None:
    """Send reminder e-mails for triggers with pending/pending_admin status."""
    wf_id = get_workflow_id()
    log_path = SETTINGS.workflows_dir / f"{wf_id}.jsonl"
    statuses: dict[str, str] = {}
    if log_path.exists():
        try:
            with log_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    eid = rec.get("event_id")
                    if eid:
                        statuses[eid] = rec.get("status")
        except Exception:
            statuses = {}

    for trig in triggers:
        payload = trig.get("payload") or {}
        event_id = payload.get("event_id") or trig.get("event_id")
        if not event_id:
            continue
        
        # Check if this event needs a reminder
        current_status = statuses.get(event_id)
        if current_status not in {status_defs.PENDING, status_defs.PENDING_ADMIN}:
            continue
        
        # Extract recipient from trigger structure
        recipient = (
            trig.get("recipient") or 
            trig.get("creator") or
            payload.get("creatorEmail") or
            (payload.get("creator") or {}).get("email") or
            (payload.get("organizer") or {}).get("email")
        )
        
        if not recipient:
            continue
        
        # Extract missing fields info
        missing = trig.get("missing", [])
        if not missing:
            # Check if we can determine what's missing
            if not payload.get("company_name"):
                missing.append("company_name")
            if not payload.get("domain"):
                missing.append("domain")
        
        if not missing:
            continue
        
        try:
            email = build_reminder_email(
                source=trig.get("source", "calendar"),
                recipient=recipient,
                missing=missing,
            )
            email_sender.send(
                to=email["recipient"],
                subject=email["subject"],
                body=email["body"],
            )
            
            reminder_log = _reminder_log_path()
            reminder_log.parent.mkdir(parents=True, exist_ok=True)
            append_jsonl(
                reminder_log,
                {
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "status": "reminder_sent",
                    "event_id": event_id,
                    "source": trig.get("source", "calendar"),
                    "recipient": recipient,
                    "missing": missing,
                },
            )
        except Exception as e:
            # Log the error but continue with other triggers
            log_event({
                "event_id": event_id,
                "status": "reminder_send_failed",
                "error": str(e),
                "severity": "warning"
            })


__all__ = ["ReminderScheduler", "check_and_notify"]
