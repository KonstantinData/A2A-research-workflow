# integrations/mailer.py
"""Low level SMTP helper supporting SSL and STARTTLS connections."""

from __future__ import annotations

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
import smtplib
import ssl


def _validate_recipient(recipient: str, allowed_domain: str | None) -> str:
    """Validate and normalize recipient address."""
    recipient = recipient.strip()
    if not recipient:
        raise ValueError("Recipient address must not be empty")
    
    domain_guard = (allowed_domain or "").strip().lstrip("@").lower()
    if domain_guard:
        if "@" not in recipient:
            raise ValueError("Recipient address is missing a domain part")
        recipient_domain = recipient.rsplit("@", 1)[-1].lower()
        if recipient_domain != domain_guard:
            raise ValueError("Recipient domain is not allowlisted")
    return recipient


def _create_message(mail_from: str, to: str, subject: str, body: str, message_id: str | None) -> MIMEMultipart:
    """Create base email message."""
    msg = MIMEMultipart()
    msg.attach(MIMEText(body, "plain", "utf-8"))
    msg["From"] = mail_from
    msg["To"] = to
    msg["Subject"] = subject
    if message_id:
        msg["Message-ID"] = message_id
    return msg


def _add_attachments(msg: MIMEMultipart, attachments: list[str] | None) -> None:
    """Add file attachments to message."""
    for path in attachments or []:
        try:
            resolved_path = Path(path).resolve()
            if not resolved_path.exists() or not resolved_path.is_file():
                continue
            
            with resolved_path.open("rb") as fh:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(fh.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{resolved_path.name}"')
            msg.attach(part)
        except (OSError, ValueError):
            continue


def _send_via_smtp(host: str, port: int, user: str, password: str, mail_from: str, recipient: str, msg: MIMEMultipart, secure: str) -> None:
    """Send message via SMTP connection."""
    try:
        if secure == "ssl":
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context) as smtp:
                smtp.login(user, password)
                smtp.sendmail(mail_from, [recipient], msg.as_string())
        elif secure == "tls":
            with smtplib.SMTP(host, port) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(user, password)
                smtp.sendmail(mail_from, [recipient], msg.as_string())
        else:
            raise ValueError(f"Unsupported secure mode: {secure}")
    except Exception as exc:
        raise RuntimeError(f"Failed to send email via {host}:{port} using {secure}") from exc


def send_email(
    host: str,
    port: int,
    user: str,
    password: str,
    mail_from: str,
    to: str,
    subject: str,
    body: str,
    secure: str = "ssl",
    attachments: list[str] | None = None,
    allowed_domain: str | None = None,
    message_id: str | None = None,
) -> None:
    """Send an e-mail via SMTP using the selected security mode."""
    recipient = _validate_recipient(to, allowed_domain)
    msg = _create_message(mail_from, recipient, subject, body, message_id)
    _add_attachments(msg, attachments)
    _send_via_smtp(host, port, user, password, mail_from, recipient, msg, secure)

