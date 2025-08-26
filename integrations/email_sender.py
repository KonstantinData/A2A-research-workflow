# integrations/email_sender.py
"""SMTP email sender utility (LIVE, strict env, no silent fallbacks)."""
from __future__ import annotations

import datetime as dt
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, Optional, Sequence
import mimetypes
import os
import smtplib
import importlib.util
import pathlib

# Structured notification logging (file-local import to avoid hard deps elsewhere)
_notifications_spec = importlib.util.spec_from_file_location(
    "a2a_notifications",
    pathlib.Path(__file__).resolve().parents[1] / "logging" / "notifications.py",
)
notifications = importlib.util.module_from_spec(_notifications_spec)
assert _notifications_spec.loader is not None
_notifications_spec.loader.exec_module(notifications)  # type: ignore[attr-defined]

# JSONL logging for reminder events
_JSONL_PATH = Path(__file__).resolve().parents[1] / "logging" / "jsonl_sink.py"
_spec = importlib.util.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]
append_jsonl = _mod.append

_REMINDER_LOG = Path("logs") / "workflows" / "reminders.jsonl"


def _env_required(name: str) -> str:
    try:
        return os.environ[name]
    except KeyError as e:
        raise RuntimeError(f"Missing required SMTP setting: {name}") from e


def _env_optional(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v is not None else default


def _bool_from_env(name: str, default_true: bool = True) -> bool:
    v = os.getenv(name)
    if v is None:
        return default_true
    return str(v).strip().lower() not in {"0", "false", "no", "off"}


def _get_settings() -> dict:
    """
    Strictly read from environment variables (set by GitHub Actions secrets/variables):
      - SMTP_HOST (required)
      - SMTP_PORT (required, int)
      - SMTP_USER (optional)
      - SMTP_PASS (optional)
      - SMTP_SECURE (optional, default true → SMTPS; "false" → STARTTLS)
    """
    host = _env_required("SMTP_HOST")
    port = int(_env_required("SMTP_PORT"))
    user = _env_optional("SMTP_USER")
    password = _env_optional("SMTP_PASS") or ""
    secure = _bool_from_env("SMTP_SECURE", default_true=True)
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "secure": secure,
    }


def send_email(
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    attachments: Optional[Iterable[Path]] = None,
    *,
    task_id: Optional[str] = None,
) -> None:
    """
    Send an email with optional attachments using SMTPS (default) or STARTTLS.

    Fails hard if required SMTP env settings are missing.
    """
    cfg = _get_settings()

    # Log intent (no secrets)
    notifications.log_email(sender, recipient, subject, task_id)

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    for path in attachments or []:
        p = Path(path)
        if not p.exists():
            # Fail loudly? For now: skip missing files but could raise if required.
            continue
        ctype, _ = mimetypes.guess_type(p.name)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        with p.open("rb") as f:
            msg.add_attachment(
                f.read(), maintype=maintype, subtype=subtype, filename=p.name
            )

    if cfg["secure"]:
        # SMTPS (implicit TLS, e.g., port 465)
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"]) as smtp:
            if cfg["user"]:
                smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)
    else:
        # STARTTLS (e.g., port 587)
        with smtplib.SMTP(cfg["host"], cfg["port"]) as smtp:
            smtp.starttls()
            if cfg["user"]:
                smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)


def send(
    *,
    to: str,
    subject: str,
    body: str,
    sender: Optional[str] = None,
    attachments: Optional[Iterable[Path]] = None,
    task_id: Optional[str] = None,
) -> None:
    """Convenience wrapper using environment defaults for the sender.

    Parameters are passed to :func:`send_email` after determining the sender
    address from environment variables (``MAIL_FROM``, ``SMTP_FROM`` or
    ``SMTP_USER``).
    """

    sender_addr = (
        sender
        or os.getenv("MAIL_FROM")
        or os.getenv("SMTP_FROM")
        or os.getenv("SMTP_USER")
        or "research-agent@condata.io"
    )
    send_email(sender_addr, to, subject, body, attachments, task_id=task_id)


def send_reminder(
    *,
    to: str,
    creator_email: str,
    creator_name: Optional[str],
    event_id: Optional[str],
    event_title: str,
    event_start: Optional[dt.datetime],
    event_end: Optional[dt.datetime],
    missing_fields: Sequence[str],
) -> None:
    """Send a formatted reminder e-mail with event context."""
    title = event_title or "Untitled Event"
    date_s = event_start.date().isoformat() if event_start else None
    start_s = event_start.strftime("%H:%M") if event_start else None
    end_s = event_end.strftime("%H:%M") if event_end else None

    event_parts = []
    if date_s:
        event_parts.append(date_s)
    if start_s:
        time_part = f"{start_s}–{end_s}" if end_s else start_s
        event_parts.append(time_part)
    elif end_s:
        event_parts.append(end_s)
    event_info = ", ".join(event_parts)

    subject = f'[Research Agent] Missing Information – Event "{title}"'
    if event_info:
        subject += f" on {event_info}"
    event_clause = f" on {event_info}" if event_info else ""

    greeting = f"Hi {creator_name}," if creator_name else "Hi there,"
    body = f"""{greeting}

this is just a quick reminder from your Internal Research Agent.

For your research request regarding "{title}"{event_clause}, I still need a bit more information:

I definitely need the following details (required):
Company:
Web domain:

If you also have these details, please include them (optional):
Email:
Phone:

Please reply to this email directly with the missing information.
You might also update the calendar entry or contact record with these details.

Once I receive the information, the process will automatically continue — no further action needed from you.

Thanks a lot for your support!

"Your Internal Research Agent"
"""

    task_id = None
    if event_start:
        task_id = f"{event_start.date().isoformat()}_{event_start.strftime('%H%M')}"
    send(to=to, subject=subject, body=body, task_id=task_id)
    append_jsonl(
        _REMINDER_LOG,
        {
            "status": "reminder_sent",
            "event_id": event_id,
            "title": event_title,
            "datetime": event_start.isoformat() if event_start else None,
            "missing_fields": list(missing_fields),
            "email_sent_to": to,
        },
    )
