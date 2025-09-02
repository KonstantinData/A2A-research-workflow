"""High‑level orchestration of the A2A research workflow.

This module exposes a convenience function :func:`run_full_workflow` that
executes the entire research pipeline end‑to‑end.  It ties together
internal research, detail enrichment, neighbour discovery, second level
customer searches, consolidation, report generation and e‑mail
notification.  The function is not used by the unit tests but serves
as an example of how to combine the various building blocks defined in
this repository into a cohesive workflow.  It honours feature flags
from :mod:`core.feature_flags` and environment variables where
appropriate.

Example
-------

The snippet below shows how to invoke the full workflow programmatically:

.. code-block:: python

    from core.full_workflow import run_full_workflow
    run_full_workflow()

This will poll Google Calendar and Contacts (unless ``USE_PUSH_TRIGGERS``
is set), perform all research steps and send a report to the creator
for each trigger.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core import consolidate as _consolidate
from core import orchestrator as _orchestrator
from core import feature_flags
from integrations import email_sender
from integrations import hubspot_api
from output import pdf_render, csv_export

from agents import (
    agent_internal_search as _internal_search,
    agent_company_detail_research as _detail_search,
    agent_external_level1_company_search as _ext_l1,
    agent_external_level2_companies_search as _ext_l2,
    agent_internal_level2_company_search as _int_l2,
)


def _ensure_output_dir() -> Path:
    out_dir = Path(os.getenv("OUTPUT_DIR", "output")) / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _maybe_upsert_and_attach(consolidated: Dict[str, Any], pdf_path: Path) -> None:
    """Perform HubSpot upsert and PDF attachment if credentials permit.

    This helper first checks for the presence of a HubSpot token.  When
    configured it creates or updates the company record using
    :func:`hubspot_api.upsert_company`.  If PDF attachment is enabled
    (``ATTACH_PDF_TO_HUBSPOT``) and a portal ID is available it will
    upload the report and associate it with the company.  Errors are
    swallowed intentionally so the pipeline continues even if HubSpot
    rejects the request or the network is unavailable.
    """
    try:
        token = os.getenv("HUBSPOT_ACCESS_TOKEN")
        if not token:
            return
        company_id = hubspot_api.upsert_company(consolidated)
        if (
            feature_flags.ATTACH_PDF_TO_HUBSPOT
            and company_id
            and pdf_path.exists()
        ):
            try:
                hubspot_api.attach_pdf(pdf_path, company_id)
            except Exception:
                pass
    except Exception:
        pass


def _send_report_email(recipient: str, pdf_path: Path) -> None:
    """Send a simple notification e‑mail with the report.

    In environments where no SMTP server is configured the call to
    :func:`email_sender.send_email` may be monkeypatched during tests.
    The subject and body are intentionally plain to avoid revealing
    sensitive information.  The PDF path is attached if present.
    """
    try:
        subject = "Your A2A research report"
        body = (
            "Hello,\n\n"
            "attached you will find the consolidated research report for your recent "
            "request. Please review the document and let us know if you have "
            "any questions.\n\n"
            "Best regards,\n"
            "A2A Research Workflow"
        )
        attachments = [str(pdf_path)] if pdf_path and pdf_path.exists() else None
        email_sender.send_email(to=recipient, subject=subject, body=body, attachments=attachments)
    except Exception:
        pass


def _process_trigger(trig: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Run all research agents for a single trigger.

    Returns the consolidated data dictionary if the pipeline completes,
    otherwise ``None`` when a required field is missing.
    """
    # Step 1: internal search (handles missing fields and reminders)
    res_internal = _internal_search.run(trig)
    # If missing required fields the status will be 'missing_fields' and
    # the orchestrator should halt further processing for this trigger.
    if res_internal.get("status") == "missing_fields":
        return None
    results: List[Dict[str, Any]] = [res_internal]
    # Step 2: find neighbours with similar classification or industry
    results.append(_ext_l1.run(trig))
    # Step 3: identify possible external customers for level 2 research
    results.append(_ext_l2.run(trig))
    # Step 4: enrich external level 2 results with internal data
    results.append(_int_l2.run(trig))
    # Step 5: compile detailed company profile and report
    results.append(_detail_search.run(trig))
    consolidated = _consolidate.consolidate(results)
    return consolidated


def run_full_workflow(
    *,
    triggers: Optional[Iterable[Dict[str, Any]]] = None,
    send_emails: bool = True,
) -> List[Dict[str, Any]]:
    """Execute the full research workflow for all triggers.

    This function orchestrates the entire pipeline.  It first obtains
    triggers either from the supplied iterable or via
    :func:`core.orchestrator.gather_triggers`.  For each trigger it
    invokes all research agents, consolidates their output, generates
    PDF and CSV reports, optionally persists the results to HubSpot and
    finally sends an e‑mail to the creator.  Completed results are
    returned as a list.  Triggers which were aborted due to missing
    information are skipped.

    Parameters
    ----------
    triggers: optional iterable
        Predefined triggers to process.  When omitted the function
        invokes :func:`core.orchestrator.gather_triggers` to poll
        Google Calendar and Contacts.
    send_emails: bool, default True
        Whether to send e‑mail notifications to the trigger creators.  Set
        to ``False`` for batch processing or testing.

    Returns
    -------
    List[Dict[str, Any]]
        Consolidated data objects for each successfully processed
        trigger.
    """
    if triggers is None:
        # Honour USE_PUSH_TRIGGERS: skip gathering when external pushes
        if feature_flags.USE_PUSH_TRIGGERS:
            triggers = []
        else:
            triggers = _orchestrator.gather_triggers()
    completed: List[Dict[str, Any]] = []
    for trig in triggers or []:
        consolidated = _process_trigger(trig)
        if not consolidated:
            continue
        out_dir = _ensure_output_dir()
        pdf_path = out_dir / "report.pdf"
        csv_path = out_dir / "data.csv"
        # Write reports
        try:
            pdf_render.render_pdf(consolidated, pdf_path)
        except Exception:
            pass
        try:
            csv_export.export_csv(consolidated.get("rows", []), csv_path)
        except Exception:
            pass
        # Upsert and attach report in HubSpot if configured
        _maybe_upsert_and_attach(consolidated, pdf_path)
        # Send e‑mail to the creator
        if send_emails:
            recipient = trig.get("creator") or trig.get("recipient") or ""
            if recipient:
                _send_report_email(recipient, pdf_path)
        # Log final status via orchestrator's logger for consistency
        try:
            _orchestrator.log_event({"status": "workflow_completed", "creator": trig.get("creator")})
            _orchestrator.log_event({"status": "artifact_pdf", "path": str(pdf_path)})
            _orchestrator.log_event({"status": "artifact_csv", "path": str(csv_path)})
        except Exception:
            pass
        completed.append(consolidated)
    if not triggers:
        # When no triggers were processed emit the no_triggers event
        try:
            _orchestrator.log_event({"status": "no_triggers", "message": "No calendar or contact events matched trigger words"})
        except Exception:
            pass
    return completed


__all__ = ["run_full_workflow"]
