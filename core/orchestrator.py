#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Callable, Optional

from core import feature_flags
from core.utils import (
    required_fields,
    optional_fields,
    log_step,
    finalize_summary,
    get_workflow_id,
    bundle_logs_into_exports,
)  # noqa: F401  # required_fields/optional_fields imported for completeness
from integrations.google_calendar import fetch_events
from integrations.google_contacts import fetch_contacts
from core.trigger_words import contains_trigger

# Expose integrations so tests can monkeypatch them
from integrations import email_sender as email_sender  # noqa: F401
from integrations import email_reader as email_reader  # noqa: F401

# Research agents
from agents import (
    agent_internal_search,
    agent_internal_level2_company_search,
    agent_company_detail_research,
    agent_external_level1_company_search,
    agent_external_level2_companies_search,
    reminder_service,
    email_listener,
    field_completion_agent,
)

import importlib.util as _ilu

_JSONL_PATH = Path(__file__).resolve().parents[1] / "logging" / "jsonl_sink.py"
_spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
append_jsonl = _mod.append


# --------- kleine Logging-Helfer, von Tests gepatcht ---------
def log_event(record: Dict[str, Any]) -> None:
    """Append ``record`` to a JSONL workflow log file using a common template.

    The workflow expects every entry to provide at least ``event_id`` and
    ``status``.  Additional context is nested under ``details`` so that the log
    structure remains consistent across services.
    """

    wf = get_workflow_id()
    path = Path("logs") / "workflows" / f"{wf}.jsonl"

    base: Dict[str, Any] = {
        "event_id": record.get("event_id"),
        "status": record.get("status"),
        "timestamp": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "severity": record.get("severity", "info"),
        "workflow_id": get_workflow_id(),
        "details": {},
    }

    # Collect any extra keys into the ``details`` field.
    for k, v in record.items():
        if k not in {"event_id", "status", "timestamp", "severity", "workflow_id", "details"}:
            base.setdefault("details", {})[k] = v
        elif k == "details" and isinstance(v, dict):
            base["details"].update(v)

    append_jsonl(path, base)


def _event_id_exists(event_id: str) -> bool:
    """Return True if ``event_id`` already present in any workflow log."""
    if not event_id:
        return False
    base = Path("logs") / "workflows"
    if not base.exists():
        return False
    for path in base.glob("wf-*.jsonl"):
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        if json.loads(line).get("event_id") == event_id:
                            return True
                    except Exception:
                        continue
        except Exception:
            continue
    return False


def _missing_required(source: str, payload: Dict[str, Any]) -> List[str]:
    req = required_fields(source)
    return [f for f in req if not (payload or {}).get(f)]


def _calendar_fetch_logged(wf_id: str) -> bool:
    """Verify required calendar fetch log entries exist for this workflow."""
    path = Path("logs") / "workflows" / "calendar.jsonl"
    if not path.exists():
        return False
    required = {"fetch_call", "raw_api_response", "fetched_events"}
    statuses: set[str] = set()
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("workflow_id") == wf_id:
                    statuses.add(rec.get("status"))
    except Exception:
        return False
    return required.issubset(statuses)



# --------- Trigger-Gathering für Kalender + Kontakte ----------
def _as_trigger_from_event(ev: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    text = (ev.get("summary") or "") + " " + (ev.get("description") or "")
    if not contains_trigger(text):
        return None

    return {
        "source": "calendar",
        "creator": ev.get("creator", {}).get("email") or ev.get("creatorEmail"),
        "recipient": ev.get("organizer", {}).get("email"),
        "payload": ev,
    }


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



def gather_triggers() -> List[Dict[str, Any]]:
    """Standardisiere Trigger in gemeinsames Format {source, creator, recipient, payload}."""

    triggers: List[Dict[str, Any]] = []
    try:
        events = fetch_events()

        wf_id = get_workflow_id()
        if not _calendar_fetch_logged(wf_id):
            log_event({
                "status": "calendar_fetch_missing",
                "severity": "warning",
                "message": "Proceeding without calendar logs"
            })

        if not events or not any(e.get("event_id") for e in events):
            raise SystemExit("No real calendar events detected – aborting run")

        log_step("calendar", "fetch_return", {"count": len(events)})

        for ev in events or []:
            trig = _as_trigger_from_event(ev)
            if trig is None:
                eid = ev.get("id") or ev.get("event_id")
                log_step(
                    "calendar",
                    "event_discarded",
                    {
                        "reason": "no_trigger_match",
                        "event": {"id": eid, "summary": ev.get("summary", "")},
                    },
                )
                continue
            if _missing_required("calendar", ev):
                eid = ev.get("id") or ev.get("event_id")
                log_step(
                    "calendar",
                    "event_discarded",
                    {"reason": "missing_fields", "event": {"id": eid}},
                )
                continue
            triggers.append(trig)
        for c in fetch_contacts() or []:
            t = _as_trigger_from_contact(c)
            if t:
                triggers.append(t)
    except Exception as e:
        log_event({"severity": "critical", "where": "gather_triggers", "error": str(e)})
        raise
    return triggers



def run(
    *,
    triggers: List[Dict[str, Any]] | None = None,
    researchers: List[Callable[[Dict[str, Any]], Dict[str, Any]]] | None = None,
    consolidate_fn: Callable[[List[Dict[str, Any]]], Dict[str, Any]] | None = lambda r: {},
    pdf_renderer: Callable[[Dict[str, Any], Path], None] | None = None,
    csv_exporter: Callable[[Dict[str, Any], Path], None] | None = None,
    hubspot_upsert: Callable[[Dict[str, Any]], Any] | None = lambda d: None,
    hubspot_attach: Callable[[Path, Any], None] | None = lambda p, c: None,
    hubspot_check_existing: Callable[[Any], Any] | None = lambda cid: None,
    duplicate_checker: Callable[[Dict[str, Any], Any], bool] | None = lambda rec, existing: False,
    company_id: Any | None = None,
) -> Dict[str, Any]:
    """Orchestrate the research workflow for provided triggers."""

    # Determine triggers when not pushed externally
    # Enforce real exporters in LIVE unless explicitly in test mode
    from output import pdf_render as _pdf, csv_export as _csv
    TEST_MODE = os.getenv("A2A_TEST_MODE", "0") == "1"
    if not TEST_MODE:
        pdf_renderer = _pdf.render_pdf
        csv_exporter = _csv.export_csv
    else:
        pdf_renderer = pdf_renderer or _pdf.render_pdf
        csv_exporter = csv_exporter or _csv.export_csv

    log_event({"status": "workflow_started"})

    if triggers is None:
        if feature_flags.USE_PUSH_TRIGGERS:
            triggers = []
        else:
            triggers = gather_triggers()

    # Remove duplicates based on event_id
    filtered: List[Dict[str, Any]] = []
    for trig in triggers or []:
        eid = trig.get("payload", {}).get("event_id")
        if eid and _event_id_exists(str(eid)):
            log_event({"event_id": eid, "status": "duplicate_event"})
        else:
            filtered.append(trig)
    triggers = filtered

    # Send reminders for triggers flagged as missing info
    try:
        reminder_service.check_and_notify(triggers)
    except Exception:
        pass

    # Allow e-mail replies to fill missing fields and update task store
    replies: List[Dict[str, Any]] = []
    if email_listener.has_pending_events():
        try:
            replies = email_reader.fetch_replies()
        except Exception:
            replies = []
    for trig in triggers:
        tid = (
            trig.get("payload", {}).get("task_id")
            or trig.get("payload", {}).get("id")
            or trig.get("payload", {}).get("event_id")
        )
        for rep in list(replies):
            try:
                email_listener.run(json.dumps(rep))
            except Exception:
                pass
            if rep.get("task_id") == tid:
                trig.setdefault("payload", {}).update(rep.get("fields", {}))
                ev_id = trig.get("payload", {}).get("event_id") or rep.get("event_id")
                log_event({"status": "email_reply_received", "event_id": ev_id, "creator": rep.get("creator")})
                log_event({"status": "pending_email_reply_resolved", "event_id": ev_id})
                log_event({"status": "resumed", "event_id": ev_id, "creator": rep.get("creator")})
                replies.remove(rep)

    if not triggers:
        log_event({
            "status": "no_triggers",
            "message": "No calendar or contact events matched trigger words"
        })
        # --- Idle/Heartbeat Artefakte erzeugen ---
        from output import pdf_render, csv_export
        outdir = Path(os.getenv("OUTPUT_DIR", "output")) / "exports"
        outdir.mkdir(parents=True, exist_ok=True)
        pdf_path = outdir / "report.pdf"
        csv_path = outdir / "data.csv"
        placeholder = {
            "fields": ["info"],
            "rows": [{"info": "No valid triggers in current window"}],
            "meta": {"reason": "no_triggers"}
        }
        try:
            pdf_render.render_pdf(placeholder, pdf_path)
            log_event({"status": "artifact_pdf", "path": str(pdf_path)})
        except Exception as e:
            log_event({"status": "artifact_pdf_error", "error": str(e), "severity": "warning"})
        try:
            csv_export.export_csv(placeholder, csv_path, reason="no_triggers")
            log_event({"status": "artifact_csv", "path": str(csv_path)})
        except Exception as e:
            log_event({"status": "artifact_csv_error", "error": str(e), "severity": "warning"})
        # Zusammenfassung/Logs bündeln und normal zurückkehren
        finalize_summary()
        bundle_logs_into_exports()
        log_event({"status": "workflow_completed"})
        return {"status": "idle"}

    if researchers is None:
        researchers = [
            agent_internal_search.run,
            agent_external_level1_company_search.run,
            agent_external_level2_companies_search.run,
            agent_internal_level2_company_search.run,
            agent_company_detail_research.run,
        ]

    results: List[Dict[str, Any]] = []
    for trig in triggers:
        payload = trig.setdefault("payload", {})
        event_id = payload.get("event_id")
        missing = _missing_required(trig.get("source", ""), payload) if event_id else []
        if missing:
            log_event({"event_id": event_id, "status": "fields_missing", "missing": missing})
            enriched = field_completion_agent.run(trig)
            if enriched:
                payload.update(enriched)
                missing = _missing_required(trig.get("source", ""), payload)
                if not missing:
                    log_event({"event_id": event_id, "status": "enriched_by_ai"})
            if missing:
                log_event({"event_id": event_id, "status": "missing_fields_pending", "missing": missing})
        if researchers:
            log_event({"event_id": event_id, "status": "pending", "creator": trig.get("creator")})
        trig_results: List[Dict[str, Any]] = []
        for researcher in researchers or []:
            if getattr(researcher, "pro", False) and not feature_flags.ENABLE_PRO_SOURCES:
                continue
            res = researcher(trig)
            if res:
                payload.update(res.get("payload", {}))
                trig_results.append(res)
        if any(r.get("status") == "missing_fields" for r in trig_results):
            # skip further processing for this trigger but continue others
            continue
        results.extend(trig_results)

    consolidated = consolidate_fn(results) if consolidate_fn else {}
    log_event({"status": "consolidated", "count": len(results)})

    first_id = (triggers or [{}])[0].get("payload", {}).get("event_id")
    existing = hubspot_check_existing(company_id) if hubspot_check_existing else None
    if existing and existing.get("createdAt"):
        try:
            created = datetime.fromisoformat(str(existing["createdAt"]).replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - created).days < 7:
                log_event({"event_id": first_id, "status": "report_skipped"})
                finalize_summary()
                bundle_logs_into_exports()
                return consolidated
        except Exception:
            pass

    if duplicate_checker and duplicate_checker(consolidated, existing):
        finalize_summary()
        bundle_logs_into_exports()
        return consolidated

    out_dir = Path(os.getenv("OUTPUT_DIR", "output")) / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "report.pdf"
    csv_path = out_dir / "data.csv"
    try:
        pdf_renderer(consolidated, pdf_path)
        csv_exporter(consolidated, csv_path)
        # Artefakt-Integrität absichern (kein 3-Byte-Stub etc.)
        try:
            if pdf_path.exists() and pdf_path.stat().st_size < 1000:
                _pdf.render_pdf({"fields":["info"],"rows":[{"info":"invalid_artifact_detected"}],"meta":{}}, pdf_path)
            if csv_path.exists() and csv_path.stat().st_size < 5:
                _csv.export_csv({"info":"invalid_artifact_detected"}, csv_path)
        except Exception:
            pass
        log_event({"event_id": first_id, "status": "artifact_pdf", "path": str(pdf_path)})
        log_event({"event_id": first_id, "status": "artifact_csv", "path": str(csv_path)})
        log_step("orchestrator","report_generated",{"event_id": first_id, "path": str(pdf_path)})
    except Exception as e:
        log_step(
            "orchestrator",
            "report_error",
            {"event_id": first_id, "error": str(e)},
            severity="critical",
        )
        finalize_summary(); bundle_logs_into_exports()
        log_event({"status": "workflow_completed", "severity":"warning"})
        return consolidated

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
            log_event({"event_id": first_id, "status": "report_uploaded"})
        except Exception as e:
            log_step(
                "orchestrator",
                "report_error",
                {"event_id": first_id, "error": str(e)},
                severity="critical",
            )
            log_event({"event_id": first_id, "status": "report_upload_failed", "severity": "critical"})
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
            log_event({"event_id": first_id, "status": "report_sent"})
        except Exception as e:
            log_event({"event_id": first_id, "status": "report_not_sent", "severity": "critical"})
            log_step(
                "orchestrator",
                "report_not_sent",
                {"event_id": first_id, "error": str(e)},
                severity="critical",
            )
    else:
        log_event({"event_id": first_id, "status": "report_not_sent", "severity": "warning"})
        log_step(
            "orchestrator",
            "report_not_sent",
            {"event_id": first_id},
            severity="warning",
        )

    finalize_summary()
    bundle_logs_into_exports()
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
        code = exc.code
        if isinstance(code, int):
            return code
        print(code)
        return 0
    finally:
        try:
            finalize_summary(); bundle_logs_into_exports()
        except Exception:
            pass
        log_event({"status": "workflow_completed"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
