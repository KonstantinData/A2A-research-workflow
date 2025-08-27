# integrations/mailer.py
"""Low level SMTP helper supporting SSL and STARTTLS connections."""

from __future__ import annotations

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
) -> None:
    """Send an e-mail via SMTP using the selected security mode.

    Parameters
    ----------
    host, port, user, password, mail_from: SMTP connection details.
    to, subject, body: Message details.
    secure: ``"ssl"`` or ``"tls"`` (STARTTLS).
    """

    msg = f"From: {mail_from}\r\nTo: {to}\r\nSubject: {subject}\r\n\r\n{body}"

    try:
        if secure == "ssl":
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context) as smtp:
                smtp.login(user, password)
                smtp.sendmail(mail_from, [to], msg)
        elif secure == "tls":
            with smtplib.SMTP(host, port) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(user, password)
                smtp.sendmail(mail_from, [to], msg)
        else:  # pragma: no cover - defensive programming
            raise ValueError(f"Unsupported secure mode: {secure}")
    except Exception as exc:  # pragma: no cover - network errors
        raise RuntimeError(
            f"Failed to send email via {host}:{port} using {secure}"
        ) from exc

