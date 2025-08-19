"""Main orchestrator for the A2A workflow."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List

from integrations import email_sender, google_calendar, google_contacts


Normalized = Dict[str, Any]


def _normalize_calendar(events: Iterable[Dict[str, Any]]) -> List[Normalized]:
    normalized: List[Normalized] = []
    for event in events:
        creator = event.get("creator")
        if not creator:
            continue
        normalized.append(
            {
                "source": "calendar",
                "creator": creator,
                "recipient": creator,
                "payload": event,
            }
        )
    return normalized


def _normalize_contacts(contacts: Iterable[Dict[str, Any]]) -> List[Normalized]:
    normalized: List[Normalized] = []
    for contact in contacts:
        emails = contact.get("emailAddresses", [])
        email = emails[0].get("value") if emails else None
        if not email:
            continue
        normalized.append(
            {
                "source": "contacts",
                "creator": email,
                "recipient": email,
                "payload": contact,
            }
        )
    return normalized


def gather_triggers(
    event_fetcher: Callable[[], Iterable[Dict[str, Any]]] = google_calendar.fetch_events,
    contact_fetcher: Callable[[], Iterable[Dict[str, Any]]] = google_contacts.fetch_contacts,
) -> List[Normalized]:
    """Gather and normalize triggers from calendar events and contacts."""

    triggers: List[Normalized] = []
    triggers.extend(_normalize_calendar(event_fetcher()))
    triggers.extend(_normalize_contacts(contact_fetcher()))
    return triggers


def run(
    event_fetcher: Callable[[], Iterable[Dict[str, Any]]] = google_calendar.fetch_events,
    contact_fetcher: Callable[[], Iterable[Dict[str, Any]]] = google_contacts.fetch_contacts,
    send: Callable[[str, str, str], None] = email_sender.send_email,
) -> List[Normalized]:
    """Entry point for orchestrating research workflow.

    Returns the list of normalized trigger payloads. Each payload results in an
    email notification to its creator.
    """

    triggers = gather_triggers(event_fetcher, contact_fetcher)
    subject = "Research workflow triggered"
    for item in triggers:
        send(item["recipient"], subject, f"Trigger source: {item['source']}")
    return triggers


__all__ = ["gather_triggers", "run"]


if __name__ == "__main__":  # pragma: no cover - manual invocation
    run()

