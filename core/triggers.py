from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core import statuses


def _as_trigger_from_event(
    event: Dict[str, Any],
    *,
    contains_trigger: Callable[[Dict[str, Any]], bool],
) -> Optional[Dict[str, Any]]:
    payload = event.get("payload") or event
    if not contains_trigger(payload):
        return None
    return {
        "source": "calendar",
        "creator": (payload.get("creator") or {}).get("email")
        or payload.get("creatorEmail"),
        "recipient": (payload.get("organizer") or {}).get("email"),
        "payload": payload,
    }


def _as_trigger_from_contact(contact: Dict[str, Any]) -> Dict[str, Any]:
    email = ""
    for item in contact.get("emailAddresses", []) or []:
        value = (item or {}).get("value")
        if value:
            email = value
            break
    return {
        "source": "contacts",
        "creator": email,
        "recipient": email,
        "payload": contact,
    }


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
    if log_event is None:
        from core.logging import log_event as default_log_event

        log_event = default_log_event
    if log_step is None:
        from core.utils import log_step as default_log_step

        log_step = default_log_step
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

    if not events or not any((event or {}).get("event_id") for event in events):
        log_event({"status": "no_calendar_events", "severity": "warning"})
        events = []

    log_step("calendar", "fetch_return", {"count": len(events)})

    triggers: List[Dict[str, Any]] = []
    for event in events:
        trigger = _as_trigger_from_event(event, contains_trigger=contains_trigger)
        if trigger is None:
            payload = event.get("payload") or event
            event_id = payload.get("event_id") or payload.get("id")
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
        triggers.append(trigger)
    return triggers


def gather_contact_triggers(
    contacts: Optional[List[Dict[str, Any]]] = None,
    *,
    fetch_contacts: Callable[[], List[Dict[str, Any]]] | None = None,
    contacts_fetch_logged: Callable[[str], Optional[str]] | None = None,
    get_workflow_id: Callable[[], str] | None = None,
    log_event: Callable[[Dict[str, Any]], None] | None = None,
) -> List[Dict[str, Any]]:
    if log_event is None:
        from core.logging import log_event as default_log_event

        log_event = default_log_event
    if fetch_contacts is None:
        from integrations.google_contacts import fetch_contacts as default_fetch_contacts

        fetch_contacts = default_fetch_contacts
    if get_workflow_id is None:
        from core.utils import get_workflow_id as default_get_workflow_id

        get_workflow_id = default_get_workflow_id

    workflow_id = get_workflow_id()

    if contacts is None:
        try:
            contacts = fetch_contacts() or []
        except Exception as exc:
            log_event(
                {
                    "status": "contacts_fetch_failed",
                    "severity": "warning",
                    "error": str(exc),
                }
            )
            if os.getenv("LIVE_MODE", "1") == "1":
                raise
            contacts = []
        code = contacts_fetch_logged(workflow_id) if contacts_fetch_logged else None
        if code:
            log_event(
                {
                    "status": f"contacts_fetch_{code}",
                    "severity": "warning",
                    "message": "Proceeding without contacts logs",
                }
            )

    if not contacts:
        log_event({"status": "no_contacts", "severity": "warning"})
        return []

    return [
        trigger
        for trigger in (_as_trigger_from_contact(contact) for contact in contacts)
        if trigger
    ]


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
    if log_event is None:
        from core.logging import log_event as default_log_event

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
        triggers.extend(
            gather_contact_triggers(
                contacts,
                fetch_contacts=fetch_contacts,
                contacts_fetch_logged=contacts_fetch_logged,
                get_workflow_id=get_workflow_id,
                log_event=log_event,
            )
        )
        return triggers
    except Exception as exc:
        log_event({"severity": "critical", "where": "gather_triggers", "error": str(exc)})
        raise


def _calendar_last_error(workflow_id: str) -> Optional[Dict[str, Any]]:
    path = Path("logs") / "workflows" / "calendar.jsonl"
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
    path = Path("logs") / "workflows" / "calendar.jsonl"
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


def _contacts_fetch_logged(workflow_id: str) -> Optional[str]:
    path = Path("logs") / "workflows" / "contacts.jsonl"
    if not path.exists():
        return "missing"
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
    if "fetch_call" in statuses_seen:
        return None
    if "google_api_client_missing" in statuses_seen:
        return "missing_client"
    if "missing_google_oauth_env" in statuses_seen or "fetch_error" in statuses_seen:
        return "oauth_error"
    return "missing"


__all__ = [
    "gather_calendar_triggers",
    "gather_contact_triggers",
    "gather_triggers",
    "_calendar_last_error",
    "_calendar_fetch_logged",
    "_contacts_fetch_logged",
]
