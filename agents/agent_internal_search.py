"""Internal search agent runtime."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from agents.internal_company.run import run as internal_run
from integrations import email_sender
from core import tasks
from core.utils import optional_fields, required_fields

import importlib.util as _ilu

_JSONL_PATH = Path(__file__).resolve().parent.parent / "logging" / "jsonl_sink.py"
_spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
append_jsonl = _mod.append

Normalized = Dict[str, Any]


def _log_agent(
    action: str, domain: str, user_email: str, artifacts: str | None = None
) -> None:
    """Write a log line for this agent."""
    date = datetime.now(timezone.utc)
    path = (
        Path("logs")
        / "agent_internal_search"
        / f"{date:%Y}"
        / f"{date:%m}"
        / f"{date:%d}.jsonl"
    )
    record = {
        "ts_utc": date.isoformat().replace("+00:00", "Z"),
        "agent": "agent_internal_search",
        "action": action,
        "company_domain": domain,
        "user_email": user_email,
    }
    if artifacts:
        record["artifacts"] = artifacts
    append_jsonl(path, record)


def _log_workflow(record: Dict[str, Any]) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    path = Path("logs") / "workflows" / f"{ts}_workflow.jsonl"
    data = dict(record)
    data.setdefault(
        "timestamp", datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    append_jsonl(path, data)


def validate_required_fields(data: dict, context: str) -> tuple[List[str], List[str]]:
    req = required_fields(context)
    opt = optional_fields()
    missing_req = [f for f in req if not data.get(f)]
    missing_opt = [f for f in opt if not data.get(f)]
    return missing_req, missing_opt


def run(trigger: Normalized) -> Normalized:
    """Run internal search workflow with missing-field handling."""
    payload = trigger.get("payload", {})
    context = trigger.get("source", "")

    # Map expected keys for downstream integrations
    payload.setdefault("company_name", payload.get("company"))
    payload.setdefault("company_domain", payload.get("domain"))
    payload.setdefault("creator_email", payload.get("email") or trigger.get("creator"))

    missing_required, missing_optional = validate_required_fields(payload, context)
    creator_email = payload.get("creator_email") or ""
    creator_name = trigger.get("creator_name")
    if creator_name:
        greeting = f"Hi {creator_name},"
    else:
        greeting = f"Hi {creator_email},"
    company = payload.get("company") or payload.get("company_name") or "Unknown"

    if missing_required:
        event_title = payload.get("title") or company
        start_raw = payload.get("start")
        end_raw = payload.get("end")
        try:
            start_dt = datetime.fromisoformat(start_raw) if start_raw else None
        except Exception:
            start_dt = None
        try:
            end_dt = datetime.fromisoformat(end_raw) if end_raw else None
        except Exception:
            end_dt = None
        missing = missing_required + missing_optional
        # Create a pending task with a unique ID so replies can be matched
        task = tasks.create_task(
            trigger=str(payload.get("event_id") or event_title),
            missing_fields=missing,
            employee_email=creator_email or "",
        )
        # Include the task ID in the reminder for correlation
        email_sender.send_reminder(
            to=creator_email,
            creator_email=creator_email,
            creator_name=creator_name,
            event_id=payload.get("event_id"),
            event_title=event_title,
            event_start=start_dt,
            event_end=end_dt,
            missing_fields=missing,
            task_id=task.get("id"),
        )
        _log_workflow(
            {
                "status": "missing_fields",
                "agent": "internal_company_research",
                "creator": creator_email,
                "missing": missing_required,
            }
        )
        _log_workflow(
            {
                "status": "reminder_sent",
                "agent": "internal_company_research",
                "to": creator_email,
                "missing": missing_required,
            }
        )
        return {
            "status": "missing_fields",
            "agent": "internal_company_research",
            "creator": trigger.get("creator"),
            "missing": missing_required,
        }

    if missing_optional:
        _log_workflow(
            {
                "status": "missing_optional_fields",
                "agent": "internal_company_research",
                "creator": creator_email,
                "missing": missing_optional,
            }
        )

    company_name = payload.get("company_name") or ""
    company_domain = payload.get("company_domain") or ""

    result = internal_run(trigger)
    payload_res = result.get("payload", {}) or {}

    # Determine if the company already exists and whether a previous report is still current.
    exists = payload_res.get("exists")
    last_report_date = payload_res.get("last_report_date")
    # Parse the last report date into a datetime object; treat None or parse failures as very old
    days_since_report: int | None = None
    last_dt: datetime | None = None
    if last_report_date:
        try:
            # Expect ISO-8601 with or without trailing Z; convert to naive UTC
            lr = last_report_date.replace("Z", "+00:00")
            last_dt = datetime.fromisoformat(str(lr))
            # Compare against current UTC time
            days_since_report = (datetime.now(timezone.utc) - last_dt).days
        except Exception:
            days_since_report = None
            last_dt = None

    # If the company exists and the report is younger than 361 days, ask the employee whether to reuse it.
    # Otherwise proceed as if the company is new or the report is outdated.
    if exists:
        if days_since_report is not None and days_since_report <= 361:
            action = "AWAIT_REQUESTOR_DECISION"
            # Send a friendly email with the last report date included
            first_name = creator_email.split("@", 1)[0]
            # Format the date in a human‑readable way; fall back to ISO string if parsing fails
            # Format the date in a human‑readable way; fall back to ISO string if parsing fails
            if last_dt:
                try:
                    date_display = last_dt.strftime("%Y-%m-%d")
                except Exception:
                    date_display = last_report_date
            else:
                date_display = last_report_date or "unknown"
            subject = f"Quick check: report for {company_name}"
            body = (
                f"Hi {first_name},\n\n"
                f"good news — we already have a report for {company_name}.\n"
                f"The latest version is from {date_display}.\n\n"
                f"What should I do next?\n\n"
                f"Reply with I USE THE EXISTING — I'll send you the PDF, and you'll also find it in HubSpot under Company → Attachments.\n\n"
                f"Reply with NEW REPORT — I'll refresh the report, add new findings, and highlight changes.\n\n"
                "Best regards,\nYour Internal Research Agent"
            )
            email_sender.send_email(to=creator_email, subject=subject, body=body)
        else:
            # Older report or unknown date – treat as no existing report
            action = "NOT_IN_CRM"
    else:
        action = "NOT_IN_CRM"

    # If the company does not exist or the report is outdated, there is no need
    # to inject classification numbers.  Downstream neighbour searches rely on
    # industry_group, industry and description only.
    # Classification codes are inferred later during detail research if required.

    artifacts_path: str | None = None
    # Emit a small artefact when optional descriptive fields are present.  The
    # artefact is used by downstream components to seed search for similar
    # companies.  It now records the industry group and industry rather than
    # classification numbers.
    if any(payload.get(k) for k in ("industry_group", "industry", "description")):
        artifacts_path = "artifacts/matching_crm_companies.json"
        Path("artifacts").mkdir(exist_ok=True)
        with open(artifacts_path, "w", encoding="utf-8") as fh:
            json.dump(
                [
                    {
                        "company_name": company_name,
                        "company_domain": company_domain,
                        "industry_group": payload.get("industry_group"),
                        "industry": payload.get("industry"),
                    }
                ],
                fh,
            )

    _log_agent(action, company_domain, creator_email, artifacts_path)

    return {
        "source": "internal_search",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": {"action": action},
    }
