# integrations/email_client.py
"""Simple e-mail client helper (LIVE, strict env, friendly tone).

Composes a friendly message listing the fields that require input from
an employee. SMTP delivery is delegated to integrations.email_sender.
"""
from __future__ import annotations

from typing import Iterable, Optional
import os

from config.env import ensure_mail_from
from core.utils import log_step

from . import email_sender


def _mail_from() -> str:
    """Require MAIL_FROM via environment (set by Actions secrets/variables)."""
    ensure_mail_from()
    try:
        return os.environ["MAIL_FROM"]
    except KeyError as e:
        raise RuntimeError("MAIL_FROM not configured") from e


def send_email(
    employee_email: str,
    missing_fields: Iterable[str],
    *,
    task_id: Optional[str] = None,
) -> None:
    """Send a notification e-mail about missing fields (friendly, deterministic)."""
    _mail_from()

    # Normalize and sort for deterministic output
    fields_list = sorted({f.strip() for f in missing_fields if f and f.strip()})
    has_fields = len(fields_list) > 0

    log_step(
        "email_client",
        "compose_missing_fields_email",
        {
            "recipient": employee_email,
            "missing_fields": fields_list,
            "has_fields": has_fields,
        },
    )

    subject = "Missing information for research"
    # Friendlier copy with bullets when available
    if has_fields:
        bullets = "\n".join(f"- {f}" for f in fields_list)
        body = (
            "Hi,\n\n"
            "to proceed with the research I’m missing the following information:\n"
            f"{bullets}\n\n"
            "If anything is unclear, just reply to this e-mail and I’ll help fill the gaps.\n\n"
            "Thanks!"
        )
    else:
        body = (
            "Hi,\n\n"
            "it looks like some information is missing, but the list was empty.\n"
            "Please reply with the exact fields you’d like me to collect or confirm.\n\n"
            "Thanks!"
        )

    kwargs = {}
    if task_id is not None:
        kwargs["task_id"] = task_id

    email_sender.send_email(to=employee_email, subject=subject, body=body, **kwargs)
