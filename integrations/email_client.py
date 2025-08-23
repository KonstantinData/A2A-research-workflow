# integrations/email_client.py
"""Simple e-mail client helper.

This module provides a convenience wrapper around :mod:`email_sender`
that composes a basic message listing the fields that require input from
an employee.  The actual SMTP sending is delegated to
``integrations.email_sender`` so configuration is shared.
"""
from __future__ import annotations

from typing import Iterable
import os

from . import email_sender


def send_email(employee_email: str, missing_fields: Iterable[str]) -> None:
    """Send a notification e-mail about missing fields.

    Parameters
    ----------
    employee_email:
        Address of the employee who should receive the notification.
    missing_fields:
        Iterable of field names that are missing from the research
        payload.
    """
    sender = (
        os.getenv("MAIL_FROM")
        or os.getenv("SMTP_FROM")
        or (os.getenv("SMTP_USER") or "")
    )
    fields = ", ".join(missing_fields)
    subject = "Missing information for research"
    body = (
        "Please provide the following missing fields: "
        f"{fields}" if fields else "No fields specified."
    )
    email_sender.send_email(sender, employee_email, subject, body)
