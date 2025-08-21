"""Main orchestrator for the A2A workflow."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence

import os

from integrations import email_sender, google_calendar, google_contacts, hubspot_api
from output import csv_export, pdf_render
from core import consolidate, feature_flags, duplicate_check

Normalized = Dict[str, Any]


def _retry(func: Callable[[], Any], retries: int = 3, base_delay: float = 1.0) -> Any:
    """Execute ``func`` with exponential backoff."""
    delay = base_delay
    for attempt in range(retries):
        try:
            return func()
        except Exception:  # pragma: no cover - errors propagated after retries
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2


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
    events = _retry(event_fetcher)
    contacts = _retry(contact_fetcher)
    triggers.extend(_normalize_calendar(events))
    triggers.extend(_normalize_contacts(contacts))
    return triggers


def run(
    event_fetcher: Callable[[], Iterable[Dict[str, Any]]] = google_calendar.fetch_events,
    contact_fetcher: Callable[[], Iterable[Dict[str, Any]]] = google_contacts.fetch_contacts,
    researchers: Sequence[Callable[[Normalized], Any]] | None = None,
    consolidate_fn: Callable[[Iterable[Any]], Any] = consolidate.consolidate,
    pdf_renderer: Callable[[Any, Path], None] = pdf_render.render_pdf,
    csv_exporter: Callable[[Any, Path], None] = csv_export.export_csv,
    hubspot_upsert: Callable[[Any], None] = hubspot_api.upsert_company,
    hubspot_attach: Callable[[Path], None] = hubspot_api.attach_pdf,
    duplicate_checker: Callable[[Dict[str, Any], Iterable[Dict[str, Any]] | None], bool] = duplicate_check.is_duplicate,
    existing_records: Iterable[Dict[str, Any]] | None = None,
    triggers: Iterable[Normalized] | None = None,
) -> Any:
    """Entry point for orchestrating the research workflow."""
    if triggers is None:
        if feature_flags.USE_PUSH_TRIGGERS:
            triggers = []
        else:
            triggers = gather_triggers(event_fetcher, contact_fetcher)

    research_results: List[Any] = []
    for trigger in triggers:
        for func in researchers or []:
            if getattr(func, "pro", False) and not feature_flags.ENABLE_PRO_SOURCES:
                continue
            research_results.append(_retry(lambda f=func, t=trigger: f(t)))

    consolidated = consolidate_fn(research_results)

    # Skip further processing if the record already exists.
    if isinstance(consolidated, dict) and duplicate_checker(consolidated, existing_records):
        return consolidated

    output_dir = Path("output/exports")
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / "report.pdf"
    csv_path = output_dir / "data.csv"

    _retry(lambda: pdf_renderer(consolidated, pdf_path))
    _retry(lambda: csv_exporter(consolidated, csv_path))

    _retry(lambda: hubspot_upsert(consolidated))
    if feature_flags.ATTACH_PDF_TO_HUBSPOT:
        _retry(lambda: hubspot_attach(pdf_path))

    recipient = os.getenv("MAIL_TO")
    if recipient:
        def _send_email() -> None:
            attachments = [
                ("report.pdf", pdf_path.read_bytes(), "application/pdf"),
                ("data.csv", csv_path.read_bytes(), "text/csv"),
            ]
            details_path = csv_path.with_name("details.csv")
            if details_path.exists():
                attachments.append(
                    ("details.csv", details_path.read_bytes(), "text/csv")
                )
            email_sender.send_email(
                recipient,
                "A2A Research Report",
                "Attached report and data.",
                attachments,
            )

        _retry(_send_email)

    return consolidated


__all__ = ["gather_triggers", "run"]


if __name__ == "__main__":  # pragma: no cover - manual invocation
    run()
