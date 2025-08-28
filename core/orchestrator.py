#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Callable

from core import feature_flags
from core.utils import (
    required_fields,
    optional_fields,
    log_step,
    finalize_summary,
    get_workflow_id,
)  # noqa: F401  # required_fields/optional_fields imported for completeness
from integrations.google_calendar import fetch_events
from integrations.google_contacts import fetch_contacts

# Expose integrations so tests can monkeypatch them
from integrations import email_sender as email_sender  # noqa: F401
from integrations import email_reader as email_reader  # noqa: F401

import importlib.util as _ilu

_JSONL_PATH = Path(__file__).resolve().parents[1] / "logging" / "jsonl_sink.py"
_spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
append_jsonl = _mod.append


# --------- kleine Logging-Helfer, von Tests gepatcht ---------
def log_event(record: Dict[str, Any]) -> None:
    """Append ``record`` to a JSONL workflow log file.

    Tests look for files named ``*_workflow.jsonl`` in ``logs/workflows``.  Each
    call therefore creates/uses a file with a timestamp to the nearest second and
    appends the provided record.
    """

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    path = Path("logs") / "workflows" / f"{ts}_workflow.jsonl"
    record = dict(record)
    record.setdefault(
        "timestamp",
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    record.setdefault("severity", "info")
    record.setdefault("workflow_id", get_workflow_id())
    append_jsonl(path, record)


# --------- Trigger-Gathering für Kalender + Kontakte ----------
def _as_trigger_from_event(ev: Dict[str, Any]) -> Dict[str, Any]:
    creator = ev.get("creator") or ev.get("creatorEmail") or ""
    if isinstance(creator, dict):
        creator = creator.get("email") or ""
    return {"source": "calendar", "creator": creator, "recipient": creator, "payload": ev}


def _as_trigger_from_contact(c: Dict[str, Any]) -> Dict[str, Any]:
    # google_contacts.scheduled_poll liefert schon Normalform,
    # aber hier unterstützen wir die einfache Rohform aus fetch_contacts() Tests.
    email = ""
    for item in c.get("emailAddresses", []) or []:
        val = (item or {}).get("value")
        if val:
            email = val
            break
    return {
        "source": "contacts",
        "creator": email,
        "recipient": email,
        "payload": c,
    }


def gather_triggers(
    fetch_events_fn: Callable[[], List[Dict[str, Any]]] = fetch_events,
    fetch_contacts_fn: Callable[[], List[Dict[str, Any]]] = fetch_contacts,
) -> List[Dict[str, Any]]:
    """Standardisiere Trigger in gemeinsames Format {source, creator, recipient, payload}."""
    triggers: List[Dict[str, Any]] = []
    try:
        for ev in fetch_events_fn() or []:
            triggers.append(_as_trigger_from_event(ev))
        for c in fetch_contacts_fn() or []:
            triggers.append(_as_trigger_from_contact(c))
    except Exception as e:
        log_event({"level": "error", "where": "gather_triggers", "error": str(e)})
        raise
    return triggers


def run(
    *,
    triggers: List[Dict[str, Any]] | None = None,
    event_fetcher: Callable[[], List[Dict[str, Any]]] = fetch_events,
    contact_fetcher: Callable[[], List[Dict[str, Any]]] = fetch_contacts,
    researchers: List[Callable[[Dict[str, Any]], Dict[str, Any]]] | None = None,
    consolidate_fn: Callable[[List[Dict[str, Any]]], Dict[str, Any]] | None = lambda r: {},
    pdf_renderer: Callable[[Dict[str, Any], Path], None] | None = lambda d, p: None,
    csv_exporter: Callable[[Dict[str, Any], Path], None] | None = lambda d, p: None,
    hubspot_upsert: Callable[[Dict[str, Any]], Any] | None = lambda d: None,
    hubspot_attach: Callable[[Path, Any], None] | None = lambda p, c: None,
    hubspot_check_existing: Callable[[Any], Any] | None = lambda cid: None,
    duplicate_checker: Callable[[Dict[str, Any], Any], bool] | None = lambda rec, existing: False,
    company_id: Any | None = None,
) -> Dict[str, Any]:
    """Orchestrate the research workflow for provided triggers."""

    # Determine triggers when not pushed externally
    if triggers is None:
        if feature_flags.USE_PUSH_TRIGGERS:
            triggers = []
        else:
            triggers = gather_triggers(event_fetcher, contact_fetcher)

    # Allow e-mail replies to fill missing fields
    try:
        replies = email_reader.fetch_replies()
    except Exception:
        replies = []
    for trig in triggers:
        tid = trig.get("payload", {}).get("id") or trig.get("payload", {}).get("event_id")
        for rep in list(replies):
            if rep.get("task_id") == tid:
                trig.setdefault("payload", {}).update(rep.get("fields", {}))
                log_event({"status": "resumed", "event_id": rep.get("task_id"), "creator": rep.get("creator")})
                replies.remove(rep)

    if not triggers:
        log_event(
            {
                "status": "no_triggers",
                "message": "No calendar or contact events matched trigger words",
            }
        )
        finalize_summary()
        raise SystemExit(0)

    results: List[Dict[str, Any]] = []
    for trig in triggers:
        if researchers:
            log_event({"status": "pending", "creator": trig.get("creator")})
        for researcher in researchers or []:
            if getattr(researcher, "pro", False) and not feature_flags.ENABLE_PRO_SOURCES:
                continue
            res = researcher(trig)
            if res:
                results.append(res)

    # Abort early if any researcher indicates missing fields
    if any(r.get("status") == "missing_fields" for r in results):
        finalize_summary()
        raise SystemExit(0)

    consolidated = consolidate_fn(results) if consolidate_fn else {}

    existing = hubspot_check_existing(company_id) if hubspot_check_existing else None
    if existing and existing.get("createdAt"):
        try:
            created = datetime.fromisoformat(str(existing["createdAt"]).replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - created).days < 7:
                log_event({"status": "report_skipped"})
                finalize_summary()
                return consolidated
        except Exception:
            pass

    if duplicate_checker and duplicate_checker(consolidated, existing):
        finalize_summary()
        return consolidated

    out_dir = Path(os.getenv("OUTPUT_DIR", "output")) / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "report.pdf"
    csv_path = out_dir / "data.csv"
    first_id = (triggers or [{}])[0].get("payload", {}).get("event_id")
    try:
        pdf_renderer and pdf_renderer(consolidated, pdf_path)
        csv_exporter and csv_exporter(consolidated, csv_path)
        if pdf_renderer:
            log_step(
                "orchestrator",
                "report_generated",
                {"event_id": first_id, "path": str(pdf_path)},
            )
    except Exception as e:
        log_step(
            "orchestrator",
            "report_error",
            {"event_id": first_id, "error": str(e)},
            severity="critical",
        )
        finalize_summary()
        raise

    if company_id is None and hubspot_upsert:
        company_id = hubspot_upsert(consolidated)

    if (
        feature_flags.ATTACH_PDF_TO_HUBSPOT
        and company_id
        and pdf_path.exists()
        and hubspot_attach
    ):
        try:
            hubspot_attach(pdf_path, company_id)
            log_event({"status": "report_uploaded"})
        except Exception as e:
            log_step(
                "orchestrator",
                "report_error",
                {"event_id": first_id, "error": str(e)},
                severity="critical",
            )
            log_event({"status": "report_upload_failed"})
            log_step(
                "orchestrator",
                "report_upload_failed",
                {"event_id": first_id},
                severity="warning",
            )

    recipient = (triggers or [{}])[0].get("recipient")
    if recipient and pdf_path.exists():
        try:
            email_sender.send_email(
                to=recipient,
                subject="Your A2A research report",
                body="Please find the attached report.",
                attachments=[str(pdf_path)],
            )
            log_event({"status": "report_sent"})
        except Exception as e:
            log_event({"status": "report_not_sent"})
            log_step(
                "orchestrator",
                "report_not_sent",
                {"event_id": first_id, "error": str(e)},
                severity="critical",
            )
    else:
        log_event({"status": "report_not_sent"})
        log_step(
            "orchestrator",
            "report_not_sent",
            {"event_id": first_id},
            severity="warning",
        )

    finalize_summary()
    return consolidated


# --------- Minimale CLI (von e2e-Test aufgerufen) -------------
def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", default="")
    parser.add_argument("--website", default="")
    args = parser.parse_args(argv)

    try:
        run()
    except SystemExit as exc:  # propagate exit code but keep logs
        return int(exc.code or 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
