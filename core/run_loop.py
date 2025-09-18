from __future__ import annotations

import json
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from core import statuses
from core.sources_registry import SOURCES


def incorporate_email_replies(
    triggers: Optional[List[Dict[str, Any]]],
    *,
    email_listener: Any,
    email_reader: Any,
    log_event: Callable[[Dict[str, Any]], None],
) -> List[Dict[str, Any]]:
    triggers = triggers or []
    replies: List[Dict[str, Any]] = []
    if email_listener.has_pending_events():
        try:
            replies = email_reader.fetch_replies()
        except Exception:
            replies = []

    for trigger in triggers:
        payload = trigger.setdefault("payload", {})
        task_id = (
            payload.get("task_id")
            or payload.get("id")
            or payload.get("event_id")
        )
        for reply in list(replies):
            try:
                email_listener.run(json.dumps(reply))
            except (ValueError, TypeError, KeyError) as e:
                log_event({
                    "status": "email_listener_error",
                    "error": str(e),
                    "severity": "warning"
                })
            if reply.get("task_id") == task_id:
                payload.update(reply.get("fields", {}))
                event_id = payload.get("event_id") or reply.get("event_id")
                log_event(
                    {
                        "status": "email_reply_received",
                        "event_id": event_id,
                        "creator": reply.get("creator"),
                    }
                )
                log_event({"status": "pending_email_reply_resolved", "event_id": event_id})
                log_event(
                    {
                        "status": "resumed",
                        "event_id": event_id,
                        "creator": reply.get("creator"),
                    }
                )
                replies.remove(reply)

    return triggers


def filter_duplicate_triggers(
    triggers: Optional[Iterable[Dict[str, Any]]],
    *,
    is_event_active: Callable[[str], bool],
    log_event: Callable[[Dict[str, Any]], None],
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for trigger in triggers or []:
        payload = trigger.get("payload", {})
        event_id = payload.get("event_id")
        if event_id and is_event_active(str(event_id)):
            log_event({"event_id": event_id, "status": "duplicate_event"})
            continue
        filtered.append(trigger)
    return filtered


def resolve_researchers(
    researchers: Optional[Sequence[Callable[[Dict[str, Any]], Dict[str, Any]]]] = None,
) -> List[Callable[[Dict[str, Any]], Dict[str, Any]]]:
    if researchers is not None:
        return list(researchers)

    return list(SOURCES)


def run_researchers(
    triggers: List[Dict[str, Any]],
    researchers: Sequence[Callable[[Dict[str, Any]], Dict[str, Any]]],
    *,
    field_completion_agent: Any,
    email_sender: Any,
    log_event: Callable[[Dict[str, Any]], None],
    missing_required: Callable[[str, Dict[str, Any]], List[str]],
    extract_company: Callable[[Optional[str]], Optional[str]],
    extract_domain: Callable[[Optional[str]], Optional[str]],
    settings: Any,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    for trigger in triggers:
        payload = trigger.setdefault("payload", {})
        event_id = payload.get("event_id")

        if not payload.get("company_name"):
            company = extract_company(payload.get("summary")) or extract_company(
                payload.get("description")
            )
            if company:
                payload["company_name"] = company
        if not payload.get("domain"):
            domain = extract_domain(payload.get("summary")) or extract_domain(
                payload.get("description")
            )
            if domain:
                payload["domain"] = domain

        if event_id:
            enriched = field_completion_agent.run(trigger) or {}
            added_fields = {key: value for key, value in enriched.items() if not payload.get(key)}
            if enriched:
                payload.update(enriched)
            missing = missing_required(trigger.get("source", ""), payload)
            if missing:
                log_event(
                    {
                        "event_id": event_id,
                        "status": statuses.PENDING,
                        "missing": missing,
                    }
                )
                
                # Extract creator email with fallbacks
                creator_email = (
                    trigger.get("creator") or 
                    payload.get("creatorEmail") or
                    (payload.get("creator") or {}).get("email") or
                    (payload.get("organizer") or {}).get("email") or
                    payload.get("organizerEmail")
                )
                
                if creator_email:
                    try:
                        email_sender.send_email(
                            to=creator_email,
                            subject="Missing information for research",
                            body="Please reply with: " + ", ".join(missing),
                            task_id=payload.get("task_id") or event_id,
                        )
                        log_event({
                            "event_id": event_id,
                            "status": "missing_fields_email_sent",
                            "to": creator_email,
                            "missing": missing
                        })
                    except (ValueError, RuntimeError, ConnectionError) as e:
                        log_event({
                            "event_id": event_id,
                            "status": "email_send_failed",
                            "error": str(e),
                            "to": creator_email,
                            "severity": "error"
                        })
                else:
                    log_event({
                        "event_id": event_id,
                        "status": "no_creator_email",
                        "severity": "warning",
                        "payload_keys": list(payload.keys())
                    })
                continue
            elif added_fields:
                log_event(
                    {
                        "event_id": event_id,
                        "status": "enriched_by_ai",
                        "fields": list(added_fields.keys()),
                    }
                )

        if researchers:
            log_event(
                {
                    "event_id": event_id,
                    "status": statuses.PENDING,
                    "creator": trigger.get("creator"),
                }
            )

        trigger_results: List[Dict[str, Any]] = []
        for researcher in researchers:
            if getattr(researcher, "pro", False) and not getattr(
                settings, "enable_pro_sources", False
            ):
                continue
            result = researcher(trigger)
            if result:
                payload.update(result.get("payload", {}))
                trigger_results.append(result)

        if any(res.get("status") == "missing_fields" for res in trigger_results):
            continue

        results.extend(trigger_results)

    return results


def notify_reminders(
    triggers: Sequence[Dict[str, Any]],
    *,
    reminder_service: Any,
) -> None:
    try:
        reminder_service.check_and_notify(triggers)
    except Exception:
        pass


def first_event_id(triggers: Sequence[Dict[str, Any]] | None) -> Any:
    if not triggers:
        return None
    payload = (triggers[0].get("payload") or {}) if triggers else {}
    return payload.get("event_id")


__all__ = [
    "incorporate_email_replies",
    "filter_duplicate_triggers",
    "resolve_researchers",
    "run_researchers",
    "notify_reminders",
    "first_event_id",
]
