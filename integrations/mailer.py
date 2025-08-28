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
) -> None:
    """Send an e-mail via SMTP using the selected security mode.

    Parameters
    ----------
    host, port, user, password, mail_from: SMTP connection details.
    to, subject, body: Message details.
    secure: ``"ssl"`` or ``"tls"`` (STARTTLS).
    attachments: optional list of file paths to include.
    """

    msg = MIMEMultipart()
    msg.attach(MIMEText(body, "plain", "utf-8"))
    msg["From"] = mail_from
    msg["To"] = to
    msg["Subject"] = subject

    for path in attachments or []:
        p = Path(path)
        try:
            with p.open("rb") as fh:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(fh.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{p.name}"')
            msg.attach(part)
        except Exception:
            # Skip unreadable attachment – higher level already logged
            continue

    try:
        if secure == "ssl":
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context) as smtp:
                smtp.login(user, password)
                smtp.sendmail(mail_from, [to], msg.as_string())
        elif secure == "tls":
            with smtplib.SMTP(host, port) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(user, password)
                smtp.sendmail(mail_from, [to], msg.as_string())
        else:  # pragma: no cover - defensive programming
            raise ValueError(f"Unsupported secure mode: {secure}")
    except Exception as exc:  # pragma: no cover - network errors
        raise RuntimeError(
            f"Failed to send email via {host}:{port} using {secure}"
        ) from exc

