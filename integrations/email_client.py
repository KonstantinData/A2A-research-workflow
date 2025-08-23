# integrations/email_client.py
"""Simple e-mail client helper.

This module provides a convenience wrapper around :mod:`email_sender`
that composes a basic message listing the fields that require input from
an employee.  The actual SMTP sending is delegated to
``integrations.email_sender`` so configuration is shared.
"""
from __future__ import annotations

from typing import Iterable, Optional
import os

from . import email_sender


def send_email(
    employee_email: str,
    missing_fields: Iterable[str],
    *,
    task_id: Optional[str] = None,
) -> None:
    """Send a notification e-mail about missing fields.

    The function composes a short message listing the ``missing_fields``
    and delegates actual delivery to :mod:`integrations.email_sender` so the
    existing SMTP configuration is reused.

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

    # Normalise and sort the fields so the e-mail output is deterministic and
    # easier to read for the recipient.
    fields_list = sorted({f for f in missing_fields if f})
    fields = ", ".join(fields_list)

    subject = "Missing information for research"
    body = (
        "Please provide the following missing fields: "
        + (fields if fields else "No fields specified.")
    )

    kwargs = {}
    if task_id is not None:
        kwargs["task_id"] = task_id
    email_sender.send_email(sender, employee_email, subject, body, **kwargs)
