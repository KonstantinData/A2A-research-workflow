"""Reminder scheduling service."""

from __future__ import annotations

import time
from datetime import datetime, time as dtime, timedelta

import os

import logging

from core import tasks, task_history
from integrations import email_client, email_sender


logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Send daily reminder e-mails for open tasks at 10:00 and escalate at 15:00."""

    @staticmethod
    def _open_tasks():
        """Return tasks that are still pending or awaiting escalation."""
        return [
            t for t in tasks.list_tasks() if t.get("status") in {"pending", "reminded"}
        ]

    def send_reminders(self) -> None:
        """Send reminder e-mails for all open tasks and record history."""
        logger.info("send_reminders job started")
        processed = 0
        try:
            for task in self._open_tasks():
                email_client.send_email(
                    task["employee_email"], task["missing_fields"], task_id=task["id"]
                )
                task_history.record_event(task["id"], "reminder_sent")
                tasks.update_task_status(task["id"], "reminded")
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
                if not task_history.has_event_since(task["id"], "reminder_sent", today_start):
                    continue
                if task_history.has_event_since(task["id"], "escalated", today_start):
                    continue
                sender = (
                    os.getenv("MAIL_FROM")
                    or os.getenv("SMTP_FROM")
                    or (os.getenv("SMTP_USER") or "")
                )
                subject = f"Escalation: no response for task {task['id']}"
                body = "No response was received for the reminder sent at 10:00."
                email_sender.send_email(
                    sender, "admin@condata.io", subject, body, task_id=task["id"]
                )
                task_history.record_event(task["id"], "escalated")
                tasks.update_task_status(task["id"], "escalated")
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
        return datetime.now()

    def _sleep(self, seconds: float) -> None:
        """Sleep for a number of seconds, isolated for testing."""
        time.sleep(seconds)


__all__ = ["ReminderScheduler"]
