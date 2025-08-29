"""Utility helpers for sending notification e-mails.

The real project contains a rather feature rich mailer.  For the unit tests we
only need a very small subset which can easily be monkeypatched.  The
``send_reminder`` helper formats subject and body text in a deterministic way so
the tests can assert against it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence
import os
import time
from pathlib import Path

from .mailer import send_email as _send_email  # tatsächlicher SMTP/Provider-Client
from core.utils import log_step


def _deliver(
    to: str, subject: str, body: str, attachments: Optional[Sequence[str]] = None
) -> None:
    """Send message using environment configured SMTP credentials."""
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", 587))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    mail_from = os.environ.get("MAIL_FROM", user)
    secure = os.environ.get("SMTP_SECURE", "ssl").lower()
    _send_email(
        host,
        port,
        user,
        password,
        mail_from,
        to,
        subject,
        body,
        secure=secure,
        attachments=list(attachments or []),
    )


def send(
    *,
    to: str,
    subject: str,
    body: str,
    sender: Optional[str] = None,
    attachments: Optional[Sequence[str]] = None,
    task_id: Optional[str] = None,
) -> None:
    """
    Generische Send-Funktion, die Tests monkeypatchen.
    """
    try:
        _deliver(to, subject, body, attachments)
        log_step("orchestrator", "mail_sent", {"to": to, "subject": subject})
    except Exception as e:  # pragma: no cover - network errors
        log_step(
            "orchestrator",
            "mail_error",
            {"to": to, "subject": subject, "error": str(e), "event_id": task_id},
            severity="critical",
        )
        raise


def send_email(
    to: str,
    subject: str,
    body: str,
    *,
    sender: Optional[str] = None,
    attachments: Optional[Sequence[str]] = None,
    task_id: Optional[str] = None,
) -> None:
    """Wrapper around the low level mailer with logging and retries.

    ``task_id`` may be supplied for correlation so that replies can be matched
    to pending workflow items.  When provided it is logged with the message
    metadata."""

    attach_paths: list[str] = []
    body_extra = ""
    for path in attachments or []:
        p = Path(path)
        size = p.stat().st_size if p.exists() else 0
        if size <= 5 * 1024 * 1024:
            attach_paths.append(str(p))
        else:
            body_extra += f"\nDownload report: {p}"
            log_step(
                "mailer",
                "attachment_skipped_too_large",
                {"path": str(p), "size": size},
                severity="warning",
            )
    if body_extra:
        body = f"{body}\n\n{body_extra.strip()}"

    delays = [5, 15, 45]
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            _deliver(to, subject, body, attach_paths)
            log_step("orchestrator", "mail_sent", {"to": to, "subject": subject})
            return
        except Exception as e:  # pragma: no cover - network errors
            last_exc = e
            if attempt < 2:
                time.sleep(delays[attempt])
            else:
                log_step(
                    "orchestrator",
                    "report_not_sent",
                    {"to": to, "subject": subject, "error": str(e), "event_id": task_id},
                    severity="critical",
                )
    if last_exc:
        raise last_exc


def send_reminder(
    *,
    to: str,
    creator_email: str,
    creator_name: Optional[str],
    event_id: Optional[str],
    event_title: str,
    event_start: Optional[datetime],
    event_end: Optional[datetime],
    missing_fields: Sequence[str],
    task_id: Optional[str] = None,
) -> None:
    """Send a reminder requesting missing information.

    In addition to the existing parameters, an optional ``task_id`` may be
    provided.  When present the task identifier is included in the subject
    line so that replies can be correlated to pending tasks.  The message
    content remains friendly and lists required and optional fields.
    """

    start_s = event_start.strftime("%Y-%m-%d, %H:%M") if event_start else ""
    end_s = event_end.strftime("%H:%M") if event_end else ""

    # Build subject: include event title and optionally the task identifier
    subject = f'[Research Agent] Missing Information – "{event_title}"'
    if start_s and end_s:
        subject += f" on {start_s.split(',')[0]}, {start_s.split(', ')[1]}–{end_s}"
    if task_id:
        subject += f" – Task {task_id}"

    req_lines = "\n".join(f"{f}:" for f in missing_fields)
    opt_lines = "\n".join(f"{f}:" for f in ["Email", "Phone"])

    greeting = f"Hi {creator_name}," if creator_name else f"Hi {creator_email},"

    body = f"""{greeting}

this is just a quick reminder from your Internal Research Agent.

For your research request regarding "{event_title}" on {start_s or 'unknown'}, {start_s.split(', ')[1] if start_s else ''}–{end_s}, I still need a bit more information:

I definitely need the following details (required):
{req_lines}

If you also have these details, please include them (optional):
{opt_lines}

Please reply to this email directly with the missing information.
You might also update the calendar entry or contact record with these details.

Once I receive the information, the process will automatically continue — no further action needed from you.

Thanks a lot for your support!

"Your Internal Research Agent"
"""

    # Allow reminders only for company domains
    if not to.lower().endswith("@condata.io"):
        log_step(
            "mailer",
            "reminder_skipped_invalid_domain",
            {"to": to},
            severity="warning",
        )
        return
    send(
        to=to,
        subject=subject,
        body=body,
        task_id=task_id or event_id,
    )


# Backwards compatibility helper used in a few places in the project.
def send_missing_info_reminder(trigger: dict) -> None:  # pragma: no cover - thin wrapper
    creator_email = trigger.get("creator")
    creator_name = trigger.get("creator_name")
    title = trigger.get("title") or "Untitled Event"
    start_iso = trigger.get("start_iso")
    end_iso = trigger.get("end_iso")
    tz = trigger.get("timezone")
    start_dt = datetime.fromisoformat(start_iso) if start_iso else None
    end_dt = datetime.fromisoformat(end_iso) if end_iso else None
    send_reminder(
        to=creator_email,
        creator_email=creator_email,
        creator_name=creator_name,
        event_id=trigger.get("event_id"),
        event_title=title,
        event_start=start_dt,
        event_end=end_dt,
        missing_fields=trigger.get("missing_required", ["Company", "Web domain"]),
    )
