"""Application level mailer that enriches outbound messages with event metadata."""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from app.core.logging import log_step

from app.core.event_store import EventStore, EventStoreError
from app.core.events import EventUpdate
from integrations.email_sender import send_email as _send_email


def _normalise_message_id(value: str | None) -> str | None:
    """Ensure *value* is formatted as a RFC5322 Message-ID."""

    if not value:
        return None
    token = value.strip()
    if not token:
        return None
    token = token.strip("<>")
    if not token:
        return None
    return f"<{token}>"


def _ensure_reference_line(body: str, event_id: str) -> str:
    """Append a visible reference line when it is missing."""

    body = body or ""
    marker = f"Reference: {event_id}".strip()
    if marker and marker.lower() in body.lower():
        return body
    separator = "\n\n" if body.strip() else ""
    return f"{body.rstrip()}" f"{separator}{marker}\n"


def _format_subject(subject: str, event_id: str) -> str:
    marker = f"[ref:{event_id}]"
    subject = subject or ""
    if marker.lower() in subject.lower():
        return subject
    subject = subject.strip()
    if subject:
        return f"{subject} {marker}"
    return marker


class EmailSender:
    """Adapter that ensures outbound mails carry correlation metadata."""

    def __init__(self, *, store: Optional[EventStore] = None) -> None:
        self._store = store or EventStore()

    def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        event_id: str,
        correlation_id: Optional[str] = None,
        attachments: Optional[Sequence[str]] = None,
        sender: Optional[str] = None,
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> Optional[str]:
        """Send an email and persist the outbound correlation identifier."""

        if not event_id:
            raise ValueError("event_id must be provided for correlated e-mails")

        headers = {"X-Event-ID": event_id}
        if extra_headers:
            headers.update({k: v for k, v in extra_headers.items() if v})

        reply_header = _normalise_message_id(correlation_id)
        if reply_header:
            headers["In-Reply-To"] = reply_header
            headers["References"] = reply_header

        enriched_subject = _format_subject(subject, event_id)
        enriched_body = _ensure_reference_line(body, event_id)

        message_id = _send_email(
            to=to,
            subject=enriched_subject,
            body=enriched_body,
            sender=sender,
            attachments=list(attachments or []),
            event_id=event_id,
            headers=headers,
        )

        if message_id:
            try:
                self._store.update(event_id, EventUpdate(correlation_id=message_id))
            except EventStoreError as exc:
                log_step(
                    "mailer",
                    "correlation_update_failed",
                    {
                        "event_id": event_id,
                        "message_id": message_id,
                        "error": str(exc),
                    },
                    severity="warning",
                )
        return message_id


__all__ = ["EmailSender"]
