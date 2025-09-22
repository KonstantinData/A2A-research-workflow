from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional

from core import statuses
from config.settings import SETTINGS


def _as_trigger_from_event(
    event: Dict[str, Any],
    *,
    contains_trigger: Callable[[Dict[str, Any]], bool],
) -> Optional[Dict[str, Any]]:
    payload = event.get("payload") or event
    if not contains_trigger(payload):
        return None
    
    # Enhanced email extraction with multiple fallbacks
    creator_email = (
        (payload.get("creator") or {}).get("email") or
        payload.get("creatorEmail") or
        (payload.get("organizer") or {}).get("email") or
        payload.get("organizerEmail")
    )
    
    recipient_email = (
        (payload.get("organizer") or {}).get("email") or
        payload.get("organizerEmail") or
        creator_email
    )
    
    return {
        "source": "calendar",
        "creator": creator_email,
        "recipient": recipient_email,
        "payload": payload,
    }





def _calendar_event_identifier(event: Dict[str, Any] | None) -> Optional[str]:
    if not isinstance(event, dict):
        return None
    if event.get("event_id"):
        return str(event["event_id"])
    payload = event.get("payload")
    if isinstance(payload, dict):
        identifier = payload.get("event_id") or payload.get("id")
        if identifier:
            return str(identifier)
    identifier = event.get("id")
    return str(identifier) if identifier else None


def gather_calendar_triggers(
    events: Optional[List[Dict[str, Any]]] = None,
    *,
    fetch_events: Callable[[], List[Dict[str, Any]]] | None = None,
    calendar_fetch_logged: Callable[[str], Optional[str]] | None = None,
    calendar_last_error: Callable[[str], Optional[Dict[str, Any]]] | None = None,
    get_workflow_id: Callable[[], str] | None = None,
    log_event: Callable[[Dict[str, Any]], None] | None = None,
    log_step: Callable[[str, str, Dict[str, Any]], None] | None = None,
    contains_trigger: Callable[[Dict[str, Any]], bool] | None = None,
) -> List[Dict[str, Any]]:
    if log_step is None:
        from app.core.logging import log_step as default_log_step

        log_step = default_log_step
    if log_event is None:
        from app.core.logging import log_step as _log_step_default

        def default_log_event(record: Dict[str, Any]) -> None:
            payload = dict(record)
            severity = payload.pop("severity", "info")
            status = str(payload.get("status") or "event").lower()
            component = payload.pop("component", "calendar")
            op = payload.pop("op", status)
            message = payload.pop("message", payload.get("msg", op))
            payload.setdefault("status", status)
            payload.setdefault("msg", message)
            payload.setdefault("component", component)
            payload.setdefault("op", op)
            _log_step_default(component, op, payload, severity=severity)

        log_event = default_log_event
    if contains_trigger is None:
        from core.trigger_words import contains_trigger as default_contains_trigger

        contains_trigger = default_contains_trigger
    if get_workflow_id is None:
        from core.utils import get_workflow_id as default_get_workflow_id

        get_workflow_id = default_get_workflow_id
    if fetch_events is None:
        from integrations.google_calendar import fetch_events as default_fetch_events

        fetch_events = default_fetch_events

    workflow_id = get_workflow_id()

    if events is None:
        events = fetch_events() or []
        if events == [] and calendar_last_error is not None:
            err = calendar_last_error(workflow_id)
            if err:
                details = {
                    key: value
                    for key, value in err.items()
                    if key
                    not in {
                        "workflow_id",
                        "trigger_source",
                        "status",
                        "severity",
                        "variant",
                    }
                }
                log_event(
                    {
                        "status": err.get("status"),
                        "severity": err.get("severity", "error"),
                        **details,
                    }
                )

    code = calendar_fetch_logged(workflow_id) if calendar_fetch_logged else None
    if code:
        log_event(
            {
                "status": f"calendar_fetch_{code}",
                "severity": "warning",
                "message": "Proceeding without calendar logs",
            }
        )

    if not events or not any(_calendar_event_identifier(event) for event in events):
        log_event({"status": "no_calendar_events", "severity": "warning"})
        events = []

    log_step("calendar", "fetch_return", {"count": len(events)})

    triggers: List[Dict[str, Any]] = []
    for event in events:
        payload = event.get("payload") or event
        event_id = _calendar_event_identifier(event)
        trigger = _as_trigger_from_event(event, contains_trigger=contains_trigger)
        if trigger is None:
            log_step(
                "calendar",
                "event_discarded",
                {
                    "reason": "no_trigger_match",
                    "event": {
                        "id": event_id,
                        "summary": payload.get("summary", ""),
                    },
                },
            )
            if event_id:
                log_event({"event_id": event_id, "status": statuses.NOT_RELEVANT})
            continue
        log_step(
            "calendar",
            "trigger_detected",
            {
                "event": {
                    "id": event_id,
                    "summary": payload.get("summary", ""),
                }
            },
        )
        triggers.append(trigger)
    return triggers





def gather_triggers(
    events: Optional[List[Dict[str, Any]]] = None,
    contacts: Optional[List[Dict[str, Any]]] = None,
    *,
    fetch_events: Callable[[], List[Dict[str, Any]]] | None = None,
    fetch_contacts: Callable[[], List[Dict[str, Any]]] | None = None,
    calendar_fetch_logged: Callable[[str], Optional[str]] | None = None,
    contacts_fetch_logged: Callable[[str], Optional[str]] | None = None,
    calendar_last_error: Callable[[str], Optional[Dict[str, Any]]] | None = None,
    get_workflow_id: Callable[[], str] | None = None,
    log_event: Callable[[Dict[str, Any]], None] | None = None,
    log_step: Callable[[str, str, Dict[str, Any]], None] | None = None,
    contains_trigger: Callable[[Dict[str, Any]], bool] | None = None,
) -> List[Dict[str, Any]]:
    if log_step is None:
        from app.core.logging import log_step as default_log_step

        log_step = default_log_step
    if log_event is None:
        from app.core.logging import log_step as _log_step_default

        def default_log_event(record: Dict[str, Any]) -> None:
            payload = dict(record)
            severity = payload.pop("severity", "info")
            status = str(payload.get("status") or "event").lower()
            component = payload.pop("component", "calendar")
            op = payload.pop("op", status)
            message = payload.pop("message", payload.get("msg", op))
            payload.setdefault("status", status)
            payload.setdefault("msg", message)
            payload.setdefault("component", component)
            payload.setdefault("op", op)
            _log_step_default(component, op, payload, severity=severity)

        log_event = default_log_event

    try:
        triggers: List[Dict[str, Any]] = []
        triggers.extend(
            gather_calendar_triggers(
                events,
                fetch_events=fetch_events,
                calendar_fetch_logged=calendar_fetch_logged,
                calendar_last_error=calendar_last_error,
                get_workflow_id=get_workflow_id,
                log_event=log_event,
                log_step=log_step,
                contains_trigger=contains_trigger,
            )
        )
        # Contacts integration removed - only calendar triggers
        return triggers
    except Exception as exc:
        log_event({"severity": "critical", "where": "gather_triggers", "error": str(exc)})
        raise


def _calendar_last_error(workflow_id: str) -> Optional[Dict[str, Any]]:
    path = SETTINGS.workflows_dir / "calendar.jsonl"
    if not path.exists():
        return None
    last: Optional[Dict[str, Any]] = None
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                if record.get("workflow_id") == workflow_id and record.get("severity") == "error":
                    last = record
    except Exception:
        return None
    return last


def _calendar_fetch_logged(workflow_id: str) -> Optional[str]:
    path = SETTINGS.workflows_dir / "calendar.jsonl"
    if not path.exists():
        return "missing"
    required = {"fetch_ok"}
    statuses_seen: set[str] = set()
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                if record.get("workflow_id") == workflow_id:
                    statuses_seen.add(record.get("status"))
    except Exception:
        return "missing"
    if required.issubset(statuses_seen):
        return None
    if "google_api_client_missing" in statuses_seen:
        return "missing_client"
    if "missing_google_oauth_env" in statuses_seen or "fetch_error" in statuses_seen:
        return "oauth_error"
    return "missing"





__all__ = [
    "gather_calendar_triggers",
    "gather_triggers",
    "_calendar_last_error",
    "_calendar_fetch_logged",
]
