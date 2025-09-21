"""Structured logging helpers for the autonomous workflow."""
from __future__ import annotations

import inspect
import json
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, Optional

from config.settings import SETTINGS

from .status import EventStatus
_EventContext = Dict[str, str]
_event_context: ContextVar[Optional[_EventContext]] = ContextVar(
    "event_context", default=None
)


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


def _current_context() -> _EventContext:
    return dict(_event_context.get() or {})


def _emit(level: str, base: Dict[str, Any]) -> None:
    level_normalized = level.lower()
    context = _current_context()

    record: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level_normalized,
        "msg": str(base.pop("msg", base.get("op", ""))),
        "component": base.pop("component", "app"),
        "subsystem": base.pop("subsystem", None),
        "event_id": base.pop("event_id", None) or context.get("event_id"),
        "correlation_id": base.pop("correlation_id", None)
        or context.get("correlation_id"),
        "causation_id": base.pop("causation_id", None),
        "aggregate_id": base.pop("aggregate_id", None),
        "op": base.pop("op", None),
        "span_id": base.pop("span_id", None),
        "trace_id": base.pop("trace_id", None),
        "env": SETTINGS.env,
        "version": SETTINGS.service_version,
    }
    status = base.pop("status", None) or context.get("status")
    if status:
        record["status"] = status

    record.update(base)
    sys.stdout.write(json.dumps(record, ensure_ascii=False) + "\n")


def push_event_context(
    event_id: Optional[str],
    *,
    status: Optional[EventStatus | str] = None,
    correlation_id: Optional[str] = None,
) -> Optional[Token[Optional[_EventContext]]]:
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
    if not context:
        return None
    current = _current_context()
    combined = {**current, **context}
    return _event_context.set(combined)


def pop_event_context(token: Optional[Token[Optional[_EventContext]]]) -> None:
    if token is None:
        return
    _event_context.reset(token)


def update_event_context(
    *,
    status: Optional[EventStatus | str] = None,
    correlation_id: Optional[str] = None,
) -> None:
    context = _event_context.get()
    if not context:
        return
    normalized_status = _normalize_status(status)
    if normalized_status:
        context["status"] = normalized_status
    normalized_corr = _normalize_correlation(correlation_id)
    if normalized_corr:
        context["correlation_id"] = normalized_corr


def log_step(
    source: str,
    stage: str,
    data: Dict[str, Any],
    *,
    severity: str = "info",
) -> None:
    payload = dict(data)
    payload.setdefault("component", source)
    payload.setdefault("op", stage)
    payload.setdefault("msg", payload.get("message", stage))
    payload.pop("message", None)

    context = _current_context()
    if "event_id" not in payload and "event_id" in context:
        payload["event_id"] = context["event_id"]
    if "correlation_id" not in payload and "correlation_id" in context:
        payload["correlation_id"] = context["correlation_id"]
    if "status" not in payload and "status" in context:
        payload["status"] = context["status"]

    _emit(severity, payload)


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


__all__ = [
    "log_step",
    "push_event_context",
    "pop_event_context",
    "update_event_context",
    "with_event_context",
]
