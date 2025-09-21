"""Integration-style test covering the WAITING_USER lifecycle."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.core.events import Event
from app.core.orchestrator import Orchestrator, UserInputRequired
from app.core.status import EventStatus
from app.integrations.mailer import EmailSender


class InMemoryStore:
    """Minimal event store implementation for orchestrator tests."""

    def __init__(self, events: list[Event] | None = None) -> None:
        self._events: dict[str, Event] = {
            event.event_id: event for event in events or []
        }

    def list_pending(self, limit: int) -> list[Event]:
        pending = [event for event in self._events.values() if event.status is EventStatus.PENDING]
        pending.sort(key=lambda event: event.updated_at)
        return pending[:limit]

    def get(self, event_id: str) -> Event | None:
        return self._events.get(event_id)

    def update(self, event_id: str, patch):
        current = self._events[event_id]
        new_status = patch.status or current.status
        new_payload = patch.payload if patch.payload is not None else current.payload
        new_labels = patch.labels if patch.labels is not None else current.labels
        new_retries = patch.retries if patch.retries is not None else current.retries
        new_last_error = patch.last_error if patch.last_error is not None else current.last_error
        new_correlation = (
            patch.correlation_id if patch.correlation_id is not None else current.correlation_id
        )
        updated = replace(
            current,
            status=new_status,
            payload=new_payload,
            labels=list(new_labels),
            retries=new_retries,
            last_error=new_last_error,
            correlation_id=new_correlation,
            updated_at=datetime.now(timezone.utc),
        )
        self._events[event_id] = updated
        return updated

    def add(self, event: Event) -> None:
        self._events[event.event_id] = event


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _event(event_id: str, status: EventStatus, *, payload: dict | None = None) -> Event:
    now = datetime.now(timezone.utc)
    return Event(
        event_id=event_id,
        type="DemoEvent" if status is not None else "",
        created_at=now,
        updated_at=now,
        status=status,
        payload=payload or {},
    )


@pytest.mark.anyio("asyncio")
async def test_waiting_user_flow(monkeypatch):
    start_event = _event("demo-1", EventStatus.PENDING)
    store = InMemoryStore([start_event])

    sent_messages: list[dict[str, str]] = []

    def fake_send_email(*, to, subject, body, sender=None, attachments=None, event_id=None, headers=None):
        sent_messages.append(
            {
                "to": to,
                "subject": subject,
                "body": body,
                "event_id": event_id,
                "headers": headers or {},
            }
        )
        return "<message-out-1>"

    monkeypatch.setattr("app.integrations.mailer._send_email", fake_send_email)

    email_sender = EmailSender(store=store)  # share store so correlation updates are persisted

    attempts = {"count": 0}

    def handler(event: Event):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise UserInputRequired(
                "Need operator input",
                notification={
                    "to": "user@example.com",
                    "subject": "Follow-up needed",
                    "body": "Please provide the missing details.",
                },
            )
        return EventStatus.COMPLETED

    async def publisher(event_type: str, payload: dict):
        assert event_type == "EmailSendRequested"
        email_sender.send(
            to=payload["to"],
            subject=payload["subject"],
            body=payload["body"],
            event_id=payload["event_id"],
        )

    orchestrator = Orchestrator(
        handlers={"DemoEvent": handler},
        store=store,
        publisher=publisher,
        batch_size=5,
    )

    first_pass = await orchestrator.run_once()
    assert first_pass == 1
    assert store.get("demo-1").status is EventStatus.WAITING_USER

    assert sent_messages, "WAITING_USER transition should trigger an email notification"
    message = sent_messages[0]
    assert "[ref:demo-1]" in message["subject"].lower()
    assert "reference: demo-1" in message["body"].lower()

    reply_event = Event(
        event_id="reply-1",
        type="UserReplyReceived",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        status=EventStatus.PENDING,
        payload={"event_id": "demo-1", "message_id": "<reply-1>"},
    )
    store.add(reply_event)

    second_pass = await orchestrator.run_once()
    assert second_pass == 1
    assert store.get("reply-1").status is EventStatus.COMPLETED
    assert store.get("demo-1").status is EventStatus.PENDING

    third_pass = await orchestrator.run_once()
    assert third_pass == 1
    assert store.get("demo-1").status is EventStatus.COMPLETED

