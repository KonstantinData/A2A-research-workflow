"""Async orchestrator loop coordinating event execution."""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Iterable, Mapping, MutableMapping, Optional, Protocol

from config.settings import SETTINGS

from .logging import (
    log_step,
    pop_event_context,
    push_event_context,
    update_event_context,
)

from .event_store import (
    ConcurrencyError,
    EventStore,
    EventStoreError,
    InvalidStatusTransition,
)
from .events import Event, EventUpdate
from .status import EventStatus
from .policy.retry import MAX_ATTEMPTS, backoff as default_backoff


class _SettingsProxy:
    """Expose config settings using legacy attribute casing."""

    @property
    def LIVE_MODE(self) -> int:
        return SETTINGS.live_mode


settings = _SettingsProxy()


class UserInputRequired(RuntimeError):
    """Raised by handlers to indicate that operator input is required."""

    def __init__(
        self,
        message: str = "",
        *,
        payload: Optional[Dict[str, Any]] = None,
        notification: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.payload = payload or {}
        self.notification = notification or {}


@dataclass(slots=True)
class HandlerResult:
    """Normalized handler response used to update the event store."""

    status: EventStatus
    payload: Optional[Dict[str, Any]] = None
    labels: Optional[Iterable[str]] = None
    correlation_id: Optional[str] = None
    user_notification: Optional[Dict[str, Any]] = None

    def as_update(self, *, clear_error: bool) -> EventUpdate:
        """Convert the handler result to an ``EventUpdate`` patch."""

        update = EventUpdate(
            status=self.status,
            payload=self.payload,
            labels=list(self.labels) if self.labels is not None else None,
            correlation_id=self.correlation_id,
        )
        if clear_error:
            update.last_error = None
        return update

    def __post_init__(self) -> None:
        if self.user_notification is None:
            return
        if isinstance(self.user_notification, MappingABC) and not isinstance(
            self.user_notification, dict
        ):
            self.user_notification = dict(self.user_notification)
            return
        if not isinstance(self.user_notification, dict):
            self.user_notification = {"message": str(self.user_notification)}


class EventHandler(Protocol):
    """Protocol describing an asynchronous handler."""

    def __call__(self, event: Event) -> Awaitable[Any] | Any:
        ...


class EventStoreProtocol(Protocol):
    """Minimal interface required from the event store."""

    def list_pending(self, limit: int) -> list[Event]:
        ...

    def get(self, event_id: str) -> Optional[Event]:
        ...

    def update(self, event_id: str, patch: EventUpdate) -> Event:
        ...


Publisher = Callable[[str, Dict[str, Any]], Awaitable[None] | None]
BackoffPolicy = Callable[[int], Awaitable[float] | float]


class Orchestrator:
    """Coordinates processing of pending workflow events."""

    def __init__(
        self,
        handlers: Optional[Mapping[str, EventHandler]] = None,
        *,
        store: Optional[EventStoreProtocol] = None,
        publisher: Optional[Publisher] = None,
        batch_size: int = 10,
        max_attempts: int = MAX_ATTEMPTS,
        idle_sleep: float = 1.0,
        backoff: Optional[BackoffPolicy] = None,
    ) -> None:
        self._store: EventStoreProtocol = store or EventStore()
        self._handlers: MutableMapping[str, EventHandler] = dict(handlers or {})
        if "UserReplyReceived" not in self._handlers:
            self._handlers["UserReplyReceived"] = self._handle_user_reply_received
        self._publisher = publisher
        self._batch_size = max(1, int(batch_size))
        self._max_attempts = max(1, int(max_attempts))
        self._idle_sleep = max(0.0, float(idle_sleep))
        self._backoff = backoff or default_backoff
        self._running = False

    async def _compute_backoff(self, attempt: int) -> float:
        """Resolve the configured backoff policy for ``attempt``."""

        delay = self._backoff(attempt)
        if inspect.isawaitable(delay):
            delay = await delay
        return float(delay)

    @property
    def running(self) -> bool:
        return self._running

    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for ``event_type``."""

        self._handlers[event_type] = handler

    async def start(self) -> None:
        """Start processing events until ``stop`` is called."""

        if self._running:
            return
        self._running = True
        log_step("orchestrator", "started", {"live": settings.LIVE_MODE})
        try:
            await self.run_forever()
        finally:
            self._running = False

    def stop(self) -> None:
        """Signal the orchestrator loop to exit."""

        self._running = False

    async def run_forever(self) -> None:
        """Continuously poll for pending events and process them."""

        try:
            while self._running:
                processed = await self.run_once()
                if processed == 0:
                    await asyncio.sleep(self._idle_sleep)
        except asyncio.CancelledError:
            self._running = False
            raise

    async def run_once(self) -> int:
        """Process a single batch of pending events."""

        events = self._store.list_pending(self._batch_size)
        processed = 0
        for event in events:
            claimed = self._claim_event(event)
            if not claimed:
                continue
            try:
                await self._process_event(claimed)
            except asyncio.CancelledError:
                self._running = False
                raise
            except Exception as exc:  # pragma: no cover - defensive
                log_step(
                    "orchestrator",
                    "event_unhandled_exception",
                    {
                        "event_id": claimed.event_id,
                        "type": claimed.type,
                        "error": self._format_error(exc),
                    },
                    severity="critical",
                )
                self._fail_event(
                    claimed,
                    reason="unhandled_exception",
                    message=str(exc),
                )
            else:
                processed += 1
        return processed

    def _claim_event(self, event: Event) -> Optional[Event]:
        token = push_event_context(
            event.event_id,
            status=event.status,
            correlation_id=event.correlation_id,
        )
        try:
            try:
                claimed = self._store.update(
                    event.event_id,
                    EventUpdate(status=EventStatus.IN_PROGRESS),
                )
            except ConcurrencyError:
                log_step(
                    "orchestrator",
                    "claim_conflict",
                    {"event_id": event.event_id, "type": event.type},
                    severity="warning",
                )
                return None
            except InvalidStatusTransition as exc:
                log_step(
                    "orchestrator",
                    "claim_invalid_transition",
                    {"event_id": event.event_id, **exc.details},
                    severity="error",
                )
                return None
            except EventStoreError as exc:
                log_step(
                    "orchestrator",
                    "claim_failed",
                    {
                        "event_id": event.event_id,
                        "type": event.type,
                        "error": self._format_error(exc),
                    },
                    severity="error",
                )
                return None

            update_event_context(status=claimed.status, correlation_id=claimed.correlation_id)
            log_step(
                "orchestrator",
                "event_claimed",
                {"event_id": claimed.event_id, "type": claimed.type},
            )
            return claimed
        finally:
            pop_event_context(token)

    async def _process_event(self, event: Event) -> None:
        token = push_event_context(
            event.event_id,
            status=event.status,
            correlation_id=event.correlation_id,
        )
        try:
            handler = self._handlers.get(event.type)
            if not handler:
                log_step(
                    "orchestrator",
                    "handler_missing",
                    {"event_id": event.event_id, "type": event.type},
                    severity="error",
                )
                self._fail_event(event, reason="handler_missing", message=f"No handler registered for {event.type}")
                return

            attempt = max(0, int(event.retries))
            while attempt < self._max_attempts:
                try:
                    outcome = handler(event)
                    if inspect.isawaitable(outcome):
                        outcome = await outcome
                except UserInputRequired as exc:
                    result = HandlerResult(
                        status=EventStatus.WAITING_USER,
                        payload=exc.payload or event.payload,
                        user_notification=exc.notification,
                    )
                    await self._finalize_event(event, result)
                    return
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    attempt += 1
                    event = self._store.update(
                        event.event_id,
                        EventUpdate(
                            retries=attempt,
                            last_error=self._format_error(exc),
                        ),
                    )
                    update_event_context(status=event.status, correlation_id=event.correlation_id)
                    log_step(
                        "orchestrator",
                        "handler_error",
                        {
                            "event_id": event.event_id,
                            "type": event.type,
                            "attempt": attempt,
                            "max_attempts": self._max_attempts,
                            "error": self._format_error(exc),
                        },
                        severity="error",
                    )
                    if attempt >= self._max_attempts:
                        self._fail_event(event, reason="max_retries", message=str(exc))
                        return
                    delay = max(0.0, await self._compute_backoff(attempt))
                    if delay:
                        await asyncio.sleep(delay)
                    continue

                result = self._coerce_result(outcome)
                await self._finalize_event(event, result)
                return

            self._fail_event(event, reason="max_retries", message="retry limit reached")
        finally:
            pop_event_context(token)

    async def _finalize_event(self, event: Event, result: HandlerResult) -> None:
        clear_error = result.status in {EventStatus.COMPLETED, EventStatus.WAITING_USER}
        updated = self._store.update(event.event_id, result.as_update(clear_error=clear_error))
        update_event_context(status=updated.status, correlation_id=updated.correlation_id)

        if result.status == EventStatus.COMPLETED:
            log_step(
                "orchestrator",
                "event_completed",
                {"event_id": updated.event_id, "type": updated.type},
            )
        elif result.status == EventStatus.WAITING_USER:
            log_step(
                "orchestrator",
                "event_waiting_user",
                {
                    "event_id": updated.event_id,
                    "type": updated.type,
                    "labels": updated.labels,
                },
            )
            await self._publish(
                "EmailSendRequested",
                {"event_id": updated.event_id, **(result.user_notification or {})},
            )
        elif result.status == EventStatus.FAILED:
            log_step(
                "orchestrator",
                "event_failed",
                {"event_id": updated.event_id, "type": updated.type},
                severity="error",
            )

    def _fail_event(self, event: Event, *, reason: str, message: str) -> None:
        token = push_event_context(
            event.event_id,
            status=event.status,
            correlation_id=event.correlation_id,
        )
        try:
            try:
                failed = self._store.update(
                    event.event_id,
                    EventUpdate(
                        status=EventStatus.FAILED,
                        last_error=message,
                    ),
                )
            except EventStoreError:
                return
            update_event_context(status=failed.status, correlation_id=failed.correlation_id)
            log_step(
                "orchestrator",
                "event_failed",
                {
                    "event_id": failed.event_id,
                    "type": failed.type,
                    "reason": reason,
                },
                severity="error",
            )
        finally:
            pop_event_context(token)

    async def _publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        if not self._publisher:
            return
        try:
            result = self._publisher(event_type, payload)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:  # pragma: no cover - defensive
            log_step(
                "orchestrator",
                "publish_failed",
                {
                    "event_type": event_type,
                    "payload": payload,
                    "error": self._format_error(exc),
                },
                severity="error",
            )

    async def _handle_user_reply_received(self, event: Event) -> HandlerResult:
        token = push_event_context(
            event.event_id,
            status=event.status,
            correlation_id=event.correlation_id,
        )
        try:
            payload = event.payload or {}
            referenced_id = str(payload.get("event_id") or "").strip()
            if not referenced_id:
                return HandlerResult(status=EventStatus.COMPLETED)

            store_get = getattr(self._store, "get", None)
            current = store_get(referenced_id) if callable(store_get) else None
            if not current:
                log_step(
                    "orchestrator",
                    "user_reply_unknown_event",
                    {"referenced_event_id": referenced_id},
                    severity="warning",
                )
                return HandlerResult(status=EventStatus.COMPLETED)

            if current.status != EventStatus.WAITING_USER:
                return HandlerResult(status=EventStatus.COMPLETED)

            update = EventUpdate(
                status=EventStatus.PENDING,
                correlation_id=payload.get("message_id"),
            )

            try:
                updated = self._store.update(referenced_id, update)
            except (ConcurrencyError, InvalidStatusTransition, EventStoreError) as exc:
                log_step(
                    "orchestrator",
                    "user_reply_update_failed",
                    {
                        "referenced_event_id": referenced_id,
                        "error": self._format_error(exc),
                    },
                    severity="warning",
                )
            else:
                update_event_context(status=updated.status, correlation_id=updated.correlation_id)
                log_step(
                    "orchestrator",
                    "user_reply_received",
                    {
                        "referenced_event_id": referenced_id,
                        "message_id": payload.get("message_id"),
                    },
                )

            return HandlerResult(status=EventStatus.COMPLETED)
        finally:
            pop_event_context(token)

    def _coerce_result(self, result: Any) -> HandlerResult:
        if isinstance(result, HandlerResult):
            return result
        if result is None:
            return HandlerResult(status=EventStatus.COMPLETED)
        if isinstance(result, EventStatus):
            return HandlerResult(status=result)
        if isinstance(result, str):
            return HandlerResult(status=EventStatus(result))
        if isinstance(result, Mapping):
            status_value = result.get("status", EventStatus.COMPLETED)
            status = status_value if isinstance(status_value, EventStatus) else EventStatus(str(status_value))
            payload = result.get("payload")
            labels = result.get("labels")
            correlation_id = result.get("correlation_id")
            notification = (
                result.get("user_notification")
                or result.get("notification")
                or result.get("email")
            )
            return HandlerResult(
                status=status,
                payload=payload,
                labels=labels,
                correlation_id=correlation_id,
                user_notification=notification,
            )
        if isinstance(result, Iterable):
            items = list(result)
            if not items:
                return HandlerResult(status=EventStatus.COMPLETED)
            status_value = items[0]
            status = status_value if isinstance(status_value, EventStatus) else EventStatus(str(status_value))
            payload = items[1] if len(items) > 1 else None
            notification = items[2] if len(items) > 2 else None
            return HandlerResult(status=status, payload=payload, user_notification=notification)
        raise TypeError(f"Unsupported handler result: {type(result)!r}")

    @staticmethod
    def _format_error(exc: BaseException) -> str:
        return f"{exc.__class__.__name__}: {exc}"


__all__ = [
    "HandlerResult",
    "Orchestrator",
    "UserInputRequired",
]
