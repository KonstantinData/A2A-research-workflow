"""Main orchestrator for the A2A workflow."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional

from integrations import email_sender, google_calendar, google_contacts
from output import pdf_render, csv_export


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
    *,
    triggers: Optional[List[Normalized]] = None,
    researchers: Optional[List[Callable[[Normalized], Dict[str, Any]]]] = None,
    consolidate_fn: Optional[Callable[[List[Dict[str, Any]]], Dict[str, Any]]] = None,
    pdf_renderer: Callable[[Dict[str, Any], str], None] = pdf_render.render_pdf,
    csv_exporter: Callable[[Dict[str, Any], str], None] = csv_export.export_csv,
    hubspot_upsert: Optional[Callable[[Dict[str, Any]], None]] = None,
    hubspot_attach: Optional[Callable[[str], None]] = None,
    send: Callable[[str, str, str], None] = email_sender.send_email,
) -> List[Normalized]:
    """Coordinate the research workflow.

    This function is intentionally small but supports dependency injection so
    that tests can provide lightweight stubs for each step.
    """

    if triggers is None:
        triggers = gather_triggers(event_fetcher, contact_fetcher)
    else:
        triggers.extend(gather_triggers(event_fetcher, contact_fetcher))

    if not triggers:
        triggers = [
            {"source": "manual", "creator": "", "recipient": "", "payload": {}}
        ]

    for trigger in triggers:
        results: List[Dict[str, Any]] = []
        for researcher in researchers or []:
            results.append(researcher(trigger))

        data: Dict[str, Any] = (
            consolidate_fn(results) if consolidate_fn is not None else {}
        )

        pdf_path = "output/exports/report.pdf"
        csv_path = "output/exports/data.csv"

        if pdf_renderer is not None:
            pdf_renderer(data, pdf_path)
        if csv_exporter is not None:
            csv_exporter(data, csv_path)
        if hubspot_upsert is not None:
            hubspot_upsert(data)
        if hubspot_attach is not None and pdf_renderer is not None:
            hubspot_attach(pdf_path)

        try:
            send(
                trigger["recipient"],
                "Research workflow triggered",
                f"Trigger source: {trigger['source']}",
            )
        except Exception:  # pragma: no cover - ignore mail errors in tests
            pass

    return triggers


__all__ = ["gather_triggers", "run"]


if __name__ == "__main__":  # pragma: no cover - manual invocation
    import argparse

    parser = argparse.ArgumentParser(description="Run research orchestrator")
    parser.add_argument("--company", required=True)
    parser.add_argument("--website", required=True)
    args = parser.parse_args()

    trigger = {
        "source": "cli",
        "creator": args.company,
        "recipient": args.company,
        "payload": {"company": args.company, "website": args.website},
    }

    def researcher(trig: Normalized) -> Dict[str, Any]:
        return {"source": "researcher", "payload": trig["payload"]}

    def consolidate_fn(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            **results[0]["payload"],
            "meta": {"summary": {"source": results[0]["source"], "last_verified_at": "now"}},
        }

    run(
        triggers=[trigger],
        researchers=[researcher],
        consolidate_fn=consolidate_fn,
    )

