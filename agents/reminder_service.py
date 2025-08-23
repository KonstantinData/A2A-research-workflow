"""Reminder scheduling service."""

from __future__ import annotations

import time
from datetime import datetime, time as dtime, timedelta

from core import tasks
from integrations import email_client


class ReminderScheduler:
    """Send daily reminder e-mails for open tasks at 10:00."""

    @staticmethod
    def _open_tasks():
        """Return tasks that are still pending."""
        return [t for t in tasks.list_tasks() if t.get("status") == "pending"]

    def send_reminders(self) -> None:
        """Send reminder e-mails for all open tasks."""
        for task in self._open_tasks():
            email_client.send_email(task["employee_email"], task["missing_fields"])

    def run_forever(self) -> None:
        """Run the scheduler loop indefinitely."""
        while True:
            now = datetime.now()
            run_at = datetime.combine(now.date(), dtime(hour=10, minute=0))
            if now >= run_at:
                run_at += timedelta(days=1)
            sleep = (run_at - now).total_seconds()
            time.sleep(sleep)
            self.send_reminders()


__all__ = ["ReminderScheduler"]
