# integrations/email_sender.py
"""SMTP email sender utility."""
from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, Optional
import mimetypes
import os
import smtplib
import importlib.util
import pathlib

_notifications_spec = importlib.util.spec_from_file_location(
    "a2a_notifications",
    pathlib.Path(__file__).resolve().parents[1] / "logging" / "notifications.py",
)
notifications = importlib.util.module_from_spec(_notifications_spec)
assert _notifications_spec.loader is not None
_notifications_spec.loader.exec_module(notifications)  # type: ignore[attr-defined]


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    return val if val is not None else default


def _get_settings() -> dict:
    host = _env("EMAIL_SMTP_HOST") or _env("SMTP_HOST") or "localhost"
    port = int(_env("EMAIL_SMTP_PORT") or _env("SMTP_PORT") or "465")
    user = _env("EMAIL_SMTP_USER") or _env("SMTP_USER")
    password = _env("EMAIL_SMTP_PASS") or _env("SMTP_PASS")
    secure = (_env("SMTP_SECURE") or "true").lower() != "false"
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
    """Send an email with optional attachments using SMTP/SSL or STARTTLS based on env settings."""
    notifications.log_email(sender, recipient, subject, task_id)
    cfg = _get_settings()
    if not (os.getenv("EMAIL_SMTP_HOST") or os.getenv("SMTP_HOST")):
        return
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    for path in attachments or []:
        p = Path(path)
        if not p.exists():
            continue
        ctype, _ = mimetypes.guess_type(p.name)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        with p.open("rb") as f:
            msg.add_attachment(
                f.read(), maintype=maintype, subtype=subtype, filename=p.name
            )

    if cfg["secure"]:
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"]) as smtp:
            if cfg["user"]:
                smtp.login(cfg["user"], cfg["password"] or "")
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(cfg["host"], cfg["port"]) as smtp:
            smtp.starttls()
            if cfg["user"]:
                smtp.login(cfg["user"], cfg["password"] or "")
            smtp.send_message(msg)
