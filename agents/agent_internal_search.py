"""Internal search agent runtime."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from agents.internal_company.run import run as internal_run
from integrations import email_sender

import importlib.util as _ilu
_JSONL_PATH = Path(__file__).resolve().parent.parent / "logging" / "jsonl_sink.py"
_spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
append_jsonl = _mod.append

Normalized = Dict[str, Any]


def _log(action: str, domain: str, user_email: str, artifacts: str | None = None) -> None:
    """Write a log line for this agent."""
    date = datetime.utcnow()
    path = (
        Path("logs")
        / "agent_internal_search"
        / f"{date:%Y}"
        / f"{date:%m}"
        / f"{date:%d}.jsonl"
    )
    record = {
        "ts_utc": date.isoformat() + "Z",
        "agent": "agent_internal_search",
        "action": action,
        "company_domain": domain,
        "user_email": user_email,
    }
    if artifacts:
        record["artifacts"] = artifacts
    append_jsonl(path, record)


def run(trigger: Normalized) -> Normalized:
    """Run internal search workflow.

    The implementation here is intentionally lightweight – it delegates heavy
    lifting to ``agents.internal_company.run`` and demonstrates logging,
    artifact generation and e-mail notifications.
    """
    payload = trigger.get("payload", {})
    company_name = payload.get("company_name")
    company_domain = payload.get("company_domain")
    creator_email = payload.get("creator_email")
    if not (company_name and company_domain and creator_email):
        raise ValueError("missing required fields")

    result = internal_run(trigger)
    action = "NOT_IN_CRM" if not result.get("payload") else "AWAIT_REQUESTOR_DECISION"

    # Simple e-mail notification when a recent report exists
    if action == "AWAIT_REQUESTOR_DECISION":
        first_name = creator_email.split("@", 1)[0]
        subject = f"Quick check: report for {company_name}"
        body = (
            f"Hi {first_name},\n\n"
            f"good news — we already have a report for {company_name}.\n"
            f"The latest version is from ??.\n\n"
            f"What should I do next?\n\n"
            f"Reply with I USE THE EXISTING — I'll send you the PDF, and you'll also find it in HubSpot under Company → Attachments.\n\n"
            f"Reply with NEW REPORT — I'll refresh the report, add new findings, and highlight changes.\n\n"
            f"Best Regards,\nagent_internal_search"
        )
        email_sender.send_email(to=creator_email, subject=subject, body=body)

    artifacts_path: str | None = None
    if any(payload.get(k) for k in ("classification_number", "industry", "description")):
        artifacts_path = "artifacts/matching_crm_companies.json"
        Path("artifacts").mkdir(exist_ok=True)
        with open(artifacts_path, "w", encoding="utf-8") as fh:
            json.dump(
                [
                    {
                        "company_name": company_name,
                        "company_domain": company_domain,
                        "industry": payload.get("industry"),
                        "classification_number": payload.get("classification_number"),
                    }
                ],
                fh,
            )

    _log(action, company_domain, creator_email, artifacts_path)

    return {
        "source": "internal_search",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": {"action": action},
    }
