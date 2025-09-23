"""Thin wrapper around the integrations mailer enforcing the allowlist."""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from config.settings import email_allowed
from integrations import email_sender


def send_email(
    to: str,
    subject: str,
    body: str,
    *,
    sender: Optional[str] = None,
    attachments: Optional[Sequence[str]] = None,
    task_id: Optional[str] = None,
    event_id: Optional[str] = None,
    headers: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """Send an e-mail ensuring the recipient domain is allowlisted."""
    domain = to.rsplit("@", 1)[-1].strip().lower()
    assert email_allowed(to), f"Recipient domain '{domain}' is not allowlisted"
    return email_sender.send_email(
        to=to,
        subject=subject,
        body=body,
        sender=sender,
        attachments=attachments,
        task_id=task_id,
        event_id=event_id,
        headers=headers,
    )
