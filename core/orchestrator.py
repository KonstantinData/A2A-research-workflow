# core/orchestrator.py
"""Main orchestrator for the A2A workflow.

This module wires together the trigger fetchers (Google Calendar / Contacts),
the research agents, consolidation, export (PDF/CSV) and notifications.

It is intentionally dependency-light so it can run in GitHub Actions without
special setup beyond the required secrets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence, Optional
import importlib.util as _ilu
import datetime as dt
import os
import time

from core import consolidate, feature_flags, duplicate_check
from integrations import google_calendar, google_contacts, hubspot_api, email_sender
from output import pdf_render, csv_export

# Local JSONL sink
_JSONL_PATH = Path(__file__).resolve().parents[1] / "logging" / "jsonl_sink.py"
_spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]
append_jsonl = _mod.append

_LOG_PATH = Path("logs") / "workflows" / "reports.jsonl"

Normalized = Dict[str, Any]


# ------------------------------ utils ---------------------------------------
def _retry(fn: Callable[[], Any], retries: int = 3, delay: float = 2.0) -> Any:
    """Retry helper for flaky integrations."""
    last_exc: Optional[BaseException] = None
    for i in range(retries):
        try:
            return fn()
        except BaseException as exc:  # pragma: no cover - defensive
            last_exc = exc
            time.sleep(delay)
    if last_exc:
        raise last_exc
    return None


# ---------------------------- normalization ---------------------------------
def _normalize_events(events: Iterable[Dict[str, Any]]) -> List[Normalized]:
    norm: List[Normalized] = []
    for ev in events or []:
        creator_info = ev.get("creator")
        if isinstance(creator_info, dict):
            creator = creator_info.get("email")
        else:
            creator = creator_info
        if not creator:
            creator = ev.get("organizer", {}).get("email")
        norm.append(
            {
                "source": "calendar",
                "creator": creator,
                "recipient": creator,
                "payload": ev,
            }
        )
    return norm


def _normalize_contacts(contacts: Iterable[Dict[str, Any]]) -> List[Normalized]:
    norm: List[Normalized] = []
    for c in contacts or []:
        email: Optional[str] = None
        for item in c.get("emailAddresses", []):
            if "value" in item:
                email = item["value"]
                break
        norm.append(
            {
                "source": "contacts",
                "creator": email,
                "recipient": email,
                "payload": c,
            }
        )
    return norm


# --------------------------------- IO ---------------------------------------
def gather_triggers(
    event_fetcher: Callable[
        [], Iterable[Dict[str, Any]]
    ] = google_calendar.fetch_events,
    contact_fetcher: Callable[
        [], Iterable[Dict[str, Any]]
    ] = google_contacts.fetch_contacts,
) -> List[Normalized]:
    """Collect triggers from calendar and contacts in one list."""
    try:
        events = _retry(event_fetcher)
    except Exception:
        events = []
    try:
        contacts = _retry(contact_fetcher)
    except Exception:
        contacts = []

    triggers: List[Normalized] = []
    triggers.extend(_normalize_events(events or []))
    triggers.extend(_normalize_contacts(contacts or []))
    return triggers


# ------------------------------- pipeline -----------------------------------
def _default_researchers() -> List[Callable[[Normalized], Any]]:
    """Return a minimal set of research functions.

    Agents are optional; we import lazily to keep startup robust even if files
    are modified by the user.
    """
    funcs: List[Callable[[Normalized], Any]] = []
    try:
        from agents import (
            agent_internal_search as a1,
            agent_external_level1_company_search as a2,
            agent_external_level2_companies_search as a3,
            agent_internal_level2_company_search as a4,
            agent_internal_customer_research as a5,
        )

        funcs.extend([a1.run, a2.run, a3.run, a4.run, a5.run])
    except Exception:
        # If any agent import fails, continue with what we have.
        pass
    return funcs


def run(
    event_fetcher: Callable[
        [], Iterable[Dict[str, Any]]
    ] = google_calendar.fetch_events,
    contact_fetcher: Callable[
        [], Iterable[Dict[str, Any]]
    ] = google_contacts.fetch_contacts,
    researchers: Optional[Sequence[Callable[[Normalized], Any]]] = None,
    consolidate_fn: Callable[[Iterable[Any]], Any] = consolidate.consolidate,
    pdf_renderer: Callable[[Any, Path], None] = pdf_render.render_pdf,
    csv_exporter: Callable[[Any, Path], None] = csv_export.export_csv,
    hubspot_upsert: Callable[[Any], Optional[str]] = hubspot_api.upsert_company,
    hubspot_attach: Callable[[Path, str], None] = hubspot_api.attach_pdf,
    hubspot_check_existing: Callable[[str], Optional[Dict[str, Any]]] = hubspot_api.check_existing_report,
    company_id: Optional[str] = None,
    duplicate_checker: Callable[
        [Dict[str, Any], Optional[Iterable[Dict[str, Any]]]], bool
    ] = duplicate_check.is_duplicate,
    existing_records: Optional[Iterable[Dict[str, Any]]] = None,
    triggers: Optional[Iterable[Normalized]] = None,
) -> Any:
    """Entry point for orchestrating the research workflow."""
    if triggers is None:
        if feature_flags.USE_PUSH_TRIGGERS:
            triggers = []
        else:
            triggers = gather_triggers(event_fetcher, contact_fetcher)

    research_results: List[Any] = []
    for trig in triggers:
        for fn in (researchers if researchers is not None else _default_researchers()):
            if getattr(fn, "pro", False) and not feature_flags.ENABLE_PRO_SOURCES:
                continue
            research_results.append(_retry(lambda f=fn, t=trig: f(t)))

    # Merge results
    consolidated = consolidate_fn(research_results)

    # Guard against duplicates (best-effort)
    if duplicate_checker(consolidated, existing_records):
        return consolidated

    # Export artifacts
    out_dir = Path(os.getenv("OUTPUT_DIR", "output")) / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = out_dir / "report.pdf"
    csv_path = out_dir / "data.csv"
    pdf_renderer(consolidated, pdf_path)
    csv_exporter(consolidated, csv_path)

    # CRM + Email
    if company_id is None:
        company_id = _retry(lambda: hubspot_upsert(consolidated))

    if (
        feature_flags.ATTACH_PDF_TO_HUBSPOT
        and os.getenv("HUBSPOT_ACCESS_TOKEN")
        and os.getenv("HUBSPOT_PORTAL_ID")
        and company_id
    ):
        existing = hubspot_check_existing(company_id)
        upload_required = False
        if not existing:
            upload_required = True
        else:
            created_str = existing.get("createdAt", "")
            try:
                created_at = dt.datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except Exception:
                upload_required = True
            else:
                if (dt.datetime.now(dt.timezone.utc) - created_at).days >= 7:
                    upload_required = True

        if upload_required:
            _retry(lambda: hubspot_attach(pdf_path, company_id))
            append_jsonl(
                _LOG_PATH,
                {"status": "report_uploaded", "company_id": company_id, "file": pdf_path.name},
            )
        else:
            print(f"Skip upload: existing recent report for company {company_id}")
            append_jsonl(
                _LOG_PATH,
                {
                    "status": "report_skipped",
                    "company_id": company_id,
                    "reason": "existing recent report",
                },
            )

    def _send_email() -> None:
        sender = (
            os.getenv("MAIL_FROM")
            or os.getenv("SMTP_FROM")
            or (os.getenv("SMTP_USER") or "")
        )
        data = consolidated if isinstance(consolidated, dict) else {}
        recipient = data.get("creator") or os.getenv("MAIL_TO") or sender
        subject = "A2A Research Report"
        body = "Attached report and data."
        email_sender.send_email(
            sender, recipient, subject, body, attachments=[pdf_path, csv_path]
        )

    _retry(_send_email)

    return consolidated


__all__ = ["gather_triggers", "run"]

if __name__ == "__main__":  # pragma: no cover
    run()
