"""Simple SMTP email sender."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Iterable, Optional, Tuple

Attachment = Tuple[str, bytes, str]


def send_email(
    to_address: str,
    subject: str,
    body: str,
    attachments: Optional[Iterable[Attachment]] = None,
) -> None:
    """Send an email with optional attachments via SMTP."""
    host = os.getenv("MAIL_SMTP_HOST")
    if not host:
        raise RuntimeError("MAIL_SMTP_HOST not configured")

    port = int(os.getenv("MAIL_SMTP_PORT", "587"))
    user = os.getenv("MAIL_USER")
    password = os.getenv("MAIL_SMTP_PASS")
    sender = os.getenv("MAIL_FROM", user or "")
    secure = os.getenv("MAIL_SMTP_SECURE", "true").lower() == "true"

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)

    for filename, content, mimetype in attachments or []:
        maintype, subtype = mimetype.split("/", 1)
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    if secure:
        with smtplib.SMTP_SSL(host, port) as smtp:
            if user:
                smtp.login(user, password or "")
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls()
            if user:
                smtp.login(user, password or "")
            smtp.send_message(msg)
