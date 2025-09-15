from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


def check_existing_and_prompt(
    *,
    triggers: Optional[List[Dict[str, Any]]],
    company_id: Any,
    hubspot_check_existing: Callable[[Any], Any] | None,
    email_sender: Any,
    email_reader: Any,
    log_event: Callable[[Dict[str, Any]], None],
) -> Tuple[Any, bool]:
    existing = hubspot_check_existing(company_id) if hubspot_check_existing else None
    if not existing:
        return existing, True

    first_trigger = (triggers or [{}])[0]
    payload = first_trigger.get("payload") or {}
    first_event_id = payload.get("event_id")
    creator = first_trigger.get("creator")

    if creator:
        try:
            email_sender.send_email(
                to=creator,
                subject="Existing report found",
                body=(
                    "A report already exists for this company. "
                    "Reply with Ja to continue or Nein to skip."
                ),
                task_id=first_event_id,
            )
        except Exception:
            pass

    log_event({"event_id": first_event_id, "status": "report_exists_query"})

    decision = "yes"
    try:
        replies = email_reader.fetch_replies()
    except Exception:
        replies = []

    for reply in replies:
        if reply.get("creator") == creator:
            text = str(reply.get("text") or "").strip().lower()
            if text in {"nein", "no"}:
                decision = "no"
            elif text in {"ja", "yes"}:
                decision = "yes"
            break

    if decision != "yes":
        log_event({"event_id": first_event_id, "status": "report_skipped"})
        return existing, False

    return existing, True


def upsert_and_attach(
    *,
    consolidated: Dict[str, Any],
    company_id: Any,
    pdf_path: Path,
    hubspot_upsert: Callable[[Dict[str, Any]], Any] | None,
    hubspot_attach: Callable[[Path, Any], None] | None,
    feature_flags: Any,
    log_event: Callable[[Dict[str, Any]], None],
    log_step: Callable[[str, str, Dict[str, Any]], None],
    recovery_agent: Any,
    first_event_id: Any,
) -> Tuple[Any, bool]:
    new_company_id = company_id
    if new_company_id is None and hubspot_upsert:
        new_company_id = hubspot_upsert(consolidated)

    if (
        feature_flags.ATTACH_PDF_TO_HUBSPOT
        and new_company_id
        and pdf_path.exists()
        and hubspot_attach
    ):
        try:
            hubspot_attach(pdf_path, new_company_id)
            log_event({"event_id": first_event_id, "status": "report_uploaded"})
        except Exception as exc:
            recovery_agent.handle_failure(first_event_id, exc)
            log_event(
                {
                    "event_id": first_event_id,
                    "status": "report_upload_failed",
                    "severity": "critical",
                }
            )
            log_step(
                "orchestrator",
                "report_error",
                {"event_id": first_event_id, "error": str(exc)},
                severity="critical",
            )
            log_step(
                "orchestrator",
                "report_upload_failed",
                {"event_id": first_event_id},
                severity="warning",
            )
            return new_company_id, False

    return new_company_id, True


__all__ = ["check_existing_and_prompt", "upsert_and_attach"]
