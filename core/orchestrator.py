#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Callable, Optional
import shutil
import threading

from core import feature_flags
from core.utils import (
    required_fields,
    optional_fields,
    log_step,
    finalize_summary,
    get_workflow_id,
)  # noqa: F401  # required_fields/optional_fields imported for completeness
from core.logging import log_event
from core import exports as export_utils
from core import hubspot_ops
from core import run_loop
from core import triggers as trigger_utils
from config.settings import SETTINGS
from integrations.google_calendar import fetch_events, extract_company, extract_domain
from integrations.google_contacts import fetch_contacts
from integrations.google_oauth import build_user_credentials

# Common status definitions
from core import statuses

# Expose integrations so tests can monkeypatch them
from integrations import email_sender as email_sender  # noqa: F401
from integrations import email_reader as email_reader  # noqa: F401

# Research agents
from agents import reminder_service, email_listener, field_completion_agent, recovery_agent

CAL_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

_finalized = False
_finalized_lock = threading.Lock()


# --------- LIVE readiness assertions ---------
def _assert_live_ready() -> None:
    if os.getenv("LIVE_MODE", "1") != "1":
        return
    # v2-only
    legacy = [
        "GOOGLE_" + "CLIENT_ID",
        "GOOGLE_" + "CLIENT_SECRET",
        "GOOGLE_" + "0",
        "GOOGLE_" + "OAUTH_JSON",
        "GOOGLE_" + "CREDENTIALS_JSON",
    ]
    if any(os.getenv(k) for k in legacy):
        raise RuntimeError(
            "Legacy Google OAuth env present. Remove them; v2-only is enforced."
        )
    required = [
        "GOOGLE_REFRESH_TOKEN",
        "GOOGLE_CLIENT_ID_V2",
        "GOOGLE_CLIENT_SECRET_V2",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASS",
    ]
    if os.getenv("REQUIRE_HUBSPOT", "1") == "1":
        required.append("HUBSPOT_ACCESS_TOKEN")
    missing = [k for k in required if not os.getenv(k)]
    if not os.getenv("SMTP_FROM") and not os.getenv("MAIL_FROM"):
        missing.append("SMTP_FROM")
    if missing:
        raise RuntimeError("LIVE readiness failed; missing: " + ", ".join(missing))
    log_event({"status": "live_assertions_passed"})


def _copy_run_logs_to_export(workflow_id: str) -> None:
    src = Path("logs/workflows")
    dst = Path("output/exports/run_logs")
    # Replace any previous run logs so this directory mirrors the current run
    shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True, exist_ok=True)
    # Copy only current run files
    for name in (
        f"{workflow_id}.jsonl",
        "calendar.jsonl",
        "contacts.jsonl",
        "summary.json",
    ):
        s = src / name
        if s.exists():
            shutil.copy2(s, dst / name)


def bundle_logs_into_exports() -> None:  # pragma: no cover - backward compat
    _copy_run_logs_to_export(get_workflow_id())


def finalize_run(**event: Any) -> None:
    global _finalized
    with _finalized_lock:
        if _finalized:
            return
        _finalized = True
    try:
        finalize_summary()
        _copy_run_logs_to_export(get_workflow_id())
    finally:
        log_event({"status": "workflow_completed", **event})


def _preflight_google() -> bool:
    creds = build_user_credentials(CAL_SCOPES)
    if not creds:
        log_event(
            {
                "status": "preflight_oauth_missing",
                "provider": "google",
                "mode": "v2-only",
            }
        )
        return False
    log_event({"status": "preflight_oauth_ok", "provider": "google", "mode": "v2-only"})
    return True


def _latest_status(event_id: str) -> Optional[str]:
    """Return the last non-``fetched`` status for ``event_id`` from workflow logs."""
    if not event_id:
        return None
    base = Path("logs") / "workflows"
    if not base.exists():
        return None
    latest: Optional[str] = None
    for path in sorted(base.glob("*.jsonl")):  # Fix: Suche alle .jsonl Dateien
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if rec.get("event_id") == event_id:
                        status = rec.get("status")
                        if status != "fetched":
                            latest = status
        except Exception:
            continue
    return latest


def is_event_active(event_id: str) -> bool:
    """Return True if the latest status is final or paused for ``event_id``.

    This uses ``_latest_status`` to retrieve the most recent workflow status for
    the given ``event_id``.  Events that have reached a final state or are
    paused awaiting input should not be reprocessed, so the function returns
    ``True`` for statuses in ``FINAL_STATUSES`` or ``PAUSE_STATUSES``.  Only
    events with other statuses (e.g. ``resumed``) return ``False`` and are
    eligible for processing.
    """
    status = _latest_status(event_id)
    return status in (statuses.FINAL_STATUSES | statuses.PAUSE_STATUSES)


def _missing_required(source: str, payload: Dict[str, Any]) -> List[str]:
    req = required_fields(source)
    return [f for f in req if not (payload or {}).get(f)]


_calendar_fetch_logged = trigger_utils._calendar_fetch_logged
_contacts_fetch_logged = trigger_utils._contacts_fetch_logged
_calendar_last_error = trigger_utils._calendar_last_error


def _as_trigger_from_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    from core.trigger_words import contains_trigger as _contains_trigger

    return trigger_utils._as_trigger_from_event(
        event,
        contains_trigger=_contains_trigger,
    )


def _as_trigger_from_contact(contact: Dict[str, Any]) -> Dict[str, Any]:
    return trigger_utils._as_trigger_from_contact(contact)


def gather_calendar_triggers(
    events: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    return trigger_utils.gather_calendar_triggers(
        events,
        fetch_events=fetch_events,
        calendar_fetch_logged=_calendar_fetch_logged,
        calendar_last_error=_calendar_last_error,
        get_workflow_id=get_workflow_id,
        log_event=log_event,
        log_step=log_step,
    )


def gather_contact_triggers(
    contacts: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    return trigger_utils.gather_contact_triggers(
        contacts,
        fetch_contacts=fetch_contacts,
        contacts_fetch_logged=_contacts_fetch_logged,
        get_workflow_id=get_workflow_id,
        log_event=log_event,
    )


def gather_triggers(
    events: Optional[List[Dict[str, Any]]] = None,
    contacts: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    return trigger_utils.gather_triggers(
        events,
        contacts,
        fetch_events=fetch_events,
        fetch_contacts=fetch_contacts,
        calendar_fetch_logged=_calendar_fetch_logged,
        contacts_fetch_logged=_contacts_fetch_logged,
        calendar_last_error=_calendar_last_error,
        get_workflow_id=get_workflow_id,
        log_event=log_event,
        log_step=log_step,
    )


def run(
    *,
    triggers: List[Dict[str, Any]] | None = None,
    researchers: List[Callable[[Dict[str, Any]], Dict[str, Any]]] | None = None,
    consolidate_fn: (
        Callable[[List[Dict[str, Any]]], Dict[str, Any]] | None
    ) = lambda r: {},
    pdf_renderer: Callable[[Dict[str, Any], Path], None] | None = None,
    csv_exporter: Callable[[List[Dict[str, Any]], Path], None] | None = None,
    hubspot_upsert: Callable[[Dict[str, Any]], Any] | None = lambda d: None,
    hubspot_attach: Callable[[Path, Any], None] | None = lambda p, c: None,
    hubspot_check_existing: Callable[[Any], Any] | None = lambda cid: None,
    duplicate_checker: (
        Callable[[Dict[str, Any], Any], bool] | None
    ) = lambda rec, existing: False,
    company_id: Any | None = None,
    restart_event_id: str | None = None,
) -> Dict[str, Any]:
    """Orchestrate the research workflow for provided triggers."""
    TEST_MODE = os.getenv("A2A_TEST_MODE", "0") == "1"
    (
        pdf_renderer,
        csv_exporter,
        fallback_pdf,
        fallback_csv,
    ) = export_utils.resolve_exporters(
        pdf_renderer,
        csv_exporter,
        test_mode=TEST_MODE,
    )

    log_event({"status": "workflow_started"})

    if triggers is None:
        if feature_flags.USE_PUSH_TRIGGERS:
            triggers = []
        else:
            events = fetch_events() or []
            for event in events:
                event_id = event.get("event_id") or event.get("id")
                if event_id:
                    log_event({"event_id": event_id, "status": "fetched"})
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
            for contact in contacts:
                contact_id = (
                    contact.get("contact_id")
                    or contact.get("id")
                    or contact.get("resourceName")
                )
                if contact_id:
                    log_event({"event_id": contact_id, "status": "fetched"})
            triggers = gather_triggers(events, contacts)

    triggers = run_loop.incorporate_email_replies(
        triggers,
        email_listener=email_listener,
        email_reader=email_reader,
        log_event=log_event,
    )
    triggers = run_loop.filter_duplicate_triggers(
        triggers,
        is_event_active=is_event_active,
        log_event=log_event,
    )

    if not triggers:
        details = {
            "lookback_days": SETTINGS.cal_lookback_days,
            "lookahead_days": SETTINGS.cal_lookahead_days,
            "calendar_ids": SETTINGS.google_calendar_ids or ["primary"],
        }
        log_step("orchestrator", "no_triggers_diagnostics", details, severity="info")
        log_event(
            {
                "status": "no_triggers_diagnostics",
                "details": details,
                "severity": "info",
            }
        )
        log_event(
            {
                "status": "no_triggers",
                "message": "No calendar or contact events matched trigger words",
            }
        )
        export_utils.create_idle_artifacts(log_event=log_event)
        finalize_run()
        return {"status": "idle"}

    resolved_researchers = run_loop.resolve_researchers(researchers)
    results = run_loop.run_researchers(
        triggers,
        resolved_researchers,
        field_completion_agent=field_completion_agent,
        email_sender=email_sender,
        log_event=log_event,
        missing_required=_missing_required,
        extract_company=extract_company,
        extract_domain=extract_domain,
        feature_flags=feature_flags,
    )

    run_loop.notify_reminders(triggers, reminder_service=reminder_service)

    consolidated = consolidate_fn(results) if consolidate_fn else {}
    log_event({"status": "consolidated", "count": len(results)})

    first_event_id = run_loop.first_event_id(triggers)

    existing, should_continue = hubspot_ops.check_existing_and_prompt(
        triggers=triggers,
        company_id=company_id,
        hubspot_check_existing=hubspot_check_existing,
        email_sender=email_sender,
        email_reader=email_reader,
        log_event=log_event,
    )
    if not should_continue:
        finalize_run()
        return consolidated

    if duplicate_checker and duplicate_checker(consolidated, existing):
        finalize_run()
        return consolidated

    try:
        pdf_path, csv_path = export_utils.export_report(
            consolidated,
            first_event_id,
            pdf_renderer,
            csv_exporter,
            fallback_pdf,
            fallback_csv,
            log_event=log_event,
            log_step=log_step,
        )
    except Exception as exc:
        recovery_agent.handle_failure(first_event_id, exc)
        log_step(
            "orchestrator",
            "report_error",
            {"event_id": first_event_id, "error": str(exc)},
            severity="critical",
        )
        finalize_run(severity="warning")
        return consolidated

    try:
        company_id, upload_ok = hubspot_ops.upsert_and_attach(
            consolidated=consolidated,
            company_id=company_id,
            pdf_path=pdf_path,
            hubspot_upsert=hubspot_upsert,
            hubspot_attach=hubspot_attach,
            feature_flags=feature_flags,
            log_event=log_event,
            log_step=log_step,
            recovery_agent=recovery_agent,
            first_event_id=first_event_id,
        )
        if not upload_ok:
            finalize_run()
            return consolidated

        recipient = (triggers or [{}])[0].get("recipient")
        if recipient and pdf_path.exists():
            try:
                email_sender.send_email(
                    to=recipient,
                    subject="Your A2A research report",
                    body="Please find the attached report.",
                    attachments=[str(pdf_path)],
                )
                log_event({"event_id": first_event_id, "status": statuses.REPORT_SENT})
            except Exception as exc:
                recovery_agent.handle_failure(first_event_id, exc)
                log_event(
                    {
                        "event_id": first_event_id,
                        "status": statuses.REPORT_NOT_SENT,
                        "severity": "critical",
                    }
                )
                log_step(
                    "orchestrator",
                    "report_not_sent",
                    {"event_id": first_event_id, "error": str(exc)},
                    severity="critical",
                )
                finalize_run()
                return consolidated
        else:
            log_event(
                {
                    "event_id": first_event_id,
                    "status": statuses.REPORT_NOT_SENT,
                    "severity": "warning",
                }
            )
            log_step(
                "orchestrator",
                "report_not_sent",
                {"event_id": first_event_id},
                severity="warning",
            )
    except Exception as exc:
        recovery_agent.handle_failure(first_event_id, exc)
        finalize_run()
        return consolidated

    if restart_event_id:
        log_event({"event_id": restart_event_id, "status": "resumed"})
    finalize_run()
    return consolidated


# --------- Minimale CLI (von e2e-Test aufgerufen) -------------
def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", default="")
    parser.add_argument("--website", default="")
    args = parser.parse_args(argv)
    _assert_live_ready()
    if not _preflight_google():
        raise SystemExit(2)

    try:
        run()
    except SystemExit as exc:  # propagate exit code but keep logs
        code = exc.code
        if isinstance(code, int):
            return code
        print(code)
        return 0
    finally:
        finalize_run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
