"""Reminder scheduling service."""

from __future__ import annotations

import time
from datetime import datetime, time as dtime, timedelta

import os

from core import tasks, task_history
from integrations import email_client, email_sender


class ReminderScheduler:
    """Send daily reminder e-mails for open tasks at 10:00 and escalate at 15:00."""

    @staticmethod
    def _open_tasks():
        """Return tasks that are still pending."""
        return [t for t in tasks.list_tasks() if t.get("status") == "pending"]

    def send_reminders(self) -> None:
        """Send reminder e-mails for all open tasks and record history."""
        for task in self._open_tasks():
            email_client.send_email(task["employee_email"], task["missing_fields"])
            task_history.record_event(task["id"], "reminder_sent")

    def escalate_tasks(self) -> None:
        """Send escalation e-mails for tasks without response after reminder."""
        today_start = datetime.combine(datetime.now().date(), dtime.min)
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
            email_sender.send_email(sender, "admin@condata.io", subject, body)
            task_history.record_event(task["id"], "escalated")

    def run_forever(self) -> None:
        """Run the scheduler loop indefinitely."""
        while True:
            now = datetime.now()
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

            time.sleep((next_run - now).total_seconds())
            action()


__all__ = ["ReminderScheduler"]
