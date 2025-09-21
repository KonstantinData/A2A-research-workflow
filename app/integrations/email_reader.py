"""Adapter that turns inbound e-mails into workflow events."""

from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from email.message import Message
from typing import Dict, List, Optional

from app.core.logging import log_step

from app.core.event_bus import EventBus
from app.core.events import Event
from app.core.status import EventStatus

_SUBJECT_REF = re.compile(r"\[ref:(?P<id>[A-Z0-9\-]+)\]", re.IGNORECASE)
_BODY_REF = re.compile(r"Reference:\s*(?P<id>[A-Z0-9\-]+)", re.IGNORECASE)
_MESSAGE_ID = re.compile(r"<[^>]+>")


def _normalise_message_id(value: str | None) -> str | None:
    if not value:
        return None
    token = value.strip()
    if not token:
        return None
    token = token.strip("<>")
    if not token:
        return None
    return f"<{token}>"


def _first_message_id(raw: str | None) -> str | None:
    if not raw:
        return None
    match = _MESSAGE_ID.search(raw)
    if match:
        return _normalise_message_id(match.group(0))
    return _normalise_message_id(raw)


def _extract_body(message: Message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.is_multipart():
                continue
            if part.get_content_type() != "text/plain":
                continue
            if part.get_content_disposition() not in (None, "inline"):
                continue
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                return payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
            except Exception:
                continue
        return ""
    try:
        payload = message.get_payload(decode=True)
        if payload is None:
            return ""
        return payload.decode(message.get_content_charset() or "utf-8", errors="ignore")
    except Exception:
        return ""


def _collect_attachments(message: Message) -> List[Dict[str, str]]:
    attachments: List[Dict[str, str]] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        if part.get_content_disposition() != "attachment":
            continue
        filename = part.get_filename() or "attachment"
        try:
            payload = part.get_payload(decode=True) or b""
        except Exception:
            payload = b""
        attachments.append(
            {
                "filename": filename,
                "content_type": part.get_content_type(),
                "content": base64.b64encode(payload).decode("ascii"),
            }
        )
    return attachments


def _extract_event_id(message: Message, body: str) -> Optional[str]:
    header_id = (message.get("X-Event-ID") or "").strip()
    if header_id:
        return header_id
    subject = message.get("Subject") or ""
    subject_match = _SUBJECT_REF.search(subject)
    if subject_match:
        return subject_match.group("id").upper()
    body_match = _BODY_REF.search(body)
    if body_match:
        return body_match.group("id").upper()
    return None


class EmailReader:
    """Reads e-mails and publishes ``UserReplyReceived`` events."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def process(self, message: Message) -> Optional[Event]:
        body = _extract_body(message)
        event_id = _extract_event_id(message, body)
        if not event_id:
            log_step(
                "email_reader",
                "event_id_missing",
                {"message_id": message.get("Message-ID") or ""},
                severity="warning",
            )
            return None

        payload = {
            "event_id": event_id,
            "message_id": _first_message_id(message.get("Message-ID")),
            "in_reply_to": _first_message_id(message.get("In-Reply-To") or message.get("References")),
            "body": body,
            "attachments": _collect_attachments(message),
        }

        event = Event(
            event_id="",
            type="UserReplyReceived",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            status=EventStatus.PENDING,
            payload=payload,
        )

        return self._event_bus.publish(event)


__all__ = ["EmailReader"]
