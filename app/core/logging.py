"""Application specific logging helpers with event-aware context."""

from __future__ import annotations

import inspect
from contextlib import contextmanager
from contextvars import ContextVar, Token
from functools import wraps
from typing import Any, Callable, Dict, Optional, Protocol

from core.utils import log_step as _base_log_step

from .status import EventStatus


class _SupportsEvent(Protocol):
    event_id: str
    status: EventStatus | str
    correlation_id: Optional[str]


_EventContext = Dict[str, str]
_event_context: ContextVar[Optional[_EventContext]] = ContextVar("event_context", default=None)


def _normalize_event_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_status(value: Optional[EventStatus | str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, EventStatus):
        return value.value
    text = str(value).strip()
    return text or None


def _normalize_correlation(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _build_context(
    event_id: Optional[str],
    *,
    status: Optional[EventStatus | str] = None,
    correlation_id: Optional[str] = None,
) -> _EventContext:
    context: _EventContext = {}
    normalized_id = _normalize_event_id(event_id)
    if normalized_id:
        context["event_id"] = normalized_id
    normalized_status = _normalize_status(status)
    if normalized_status:
        context["status"] = normalized_status
    normalized_corr = _normalize_correlation(correlation_id)
    if normalized_corr:
        context["correlation_id"] = normalized_corr
    return context


def push_event_context(
    event_id: Optional[str],
    *,
    status: Optional[EventStatus | str] = None,
    correlation_id: Optional[str] = None,
) -> Optional[Token[Optional[_EventContext]]]:
    """Push a new event logging context onto the stack."""

    context_update = _build_context(event_id, status=status, correlation_id=correlation_id)
    if not context_update:
        return None
    current = _event_context.get() or {}
    combined = {**current, **context_update}
    return _event_context.set(combined)


def pop_event_context(token: Optional[Token[Optional[_EventContext]]]) -> None:
    """Restore the previous logging context."""

    if token is None:
        return
    _event_context.reset(token)


def update_event_context(
    *,
    status: Optional[EventStatus | str] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Update the active logging context in-place."""

    context = _event_context.get()
    if not context:
        return
    normalized_status = _normalize_status(status)
    if normalized_status:
        context["status"] = normalized_status
    normalized_corr = _normalize_correlation(correlation_id)
    if normalized_corr:
        context["correlation_id"] = normalized_corr


def log_step(source: str, stage: str, data: Dict[str, Any], *, severity: str = "info") -> None:
    """Proxy ``core.utils.log_step`` adding the active event context to payloads."""

    payload = dict(data)
    context = _event_context.get() or {}
    if "stage" not in payload:
        payload["stage"] = stage
    context_status = context.get("status")
    if context_status and "status" not in payload:
        payload["status"] = context_status
    context_event_id = context.get("event_id")
    if context_event_id and "event_id" not in payload:
        payload["event_id"] = context_event_id
    context_correlation = context.get("correlation_id")
    if context_correlation and "correlation_id" not in payload:
        payload["correlation_id"] = context_correlation
    _base_log_step(source, stage, payload, severity=severity)


def _resolve_from_args(
    candidate: Optional[Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    attribute: str,
) -> Optional[Any]:
    if callable(candidate):  # type: ignore[callable-arg]
        return candidate(*args, **kwargs)
    if candidate is not None:
        return candidate
    if args:
        first = args[0]
        if hasattr(first, attribute):
            return getattr(first, attribute)
    if attribute in kwargs:
        return kwargs[attribute]
    return None


def with_event_context(
    event_id: Optional[str | Callable[..., str]] = None,
    *,
    status: Optional[EventStatus | str | Callable[..., EventStatus | str]] = None,
    correlation_id: Optional[str | Callable[..., Optional[str]]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory that enriches log records emitted within the wrapped call."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                resolved_id = _normalize_event_id(
                    _resolve_from_args(event_id, args, kwargs, "event_id")
                )
                resolved_status = _normalize_status(
                    _resolve_from_args(status, args, kwargs, "status")  # type: ignore[arg-type]
                )
                resolved_corr = _normalize_correlation(
                    _resolve_from_args(correlation_id, args, kwargs, "correlation_id")
                )
                token = push_event_context(
                    resolved_id,
                    status=resolved_status,
                    correlation_id=resolved_corr,
                )
                try:
                    return await func(*args, **kwargs)
                finally:
                    pop_event_context(token)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            resolved_id = _normalize_event_id(
                _resolve_from_args(event_id, args, kwargs, "event_id")
            )
            resolved_status = _normalize_status(
                _resolve_from_args(status, args, kwargs, "status")  # type: ignore[arg-type]
            )
            resolved_corr = _normalize_correlation(
                _resolve_from_args(correlation_id, args, kwargs, "correlation_id")
            )
            token = push_event_context(
                resolved_id,
                status=resolved_status,
                correlation_id=resolved_corr,
            )
            try:
                return func(*args, **kwargs)
            finally:
                pop_event_context(token)

        return sync_wrapper

    return decorator


@contextmanager
def event_logging_context(
    event: _SupportsEvent | None,
) -> Any:
    """Context manager variant for cases where decorators are impractical."""

    if event is None:
        token = None
    else:
        token = push_event_context(
            event.event_id,
            status=event.status,
            correlation_id=event.correlation_id,
        )
    try:
        yield
    finally:
        pop_event_context(token)


__all__ = [
    "event_logging_context",
    "log_step",
    "pop_event_context",
    "push_event_context",
    "update_event_context",
    "with_event_context",
]
