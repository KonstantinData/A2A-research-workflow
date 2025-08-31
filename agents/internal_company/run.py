# agents/internal_company/run.py
"""Orchestrate internal company research fetch and normalize (LIVE)."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Iterable

from core.tasks import create_task
from core.feature_flags import ENABLE_GRAPH_STORAGE
from integrations import graph_storage  # email_client NICHT hier verwenden

from .plugins import INTERNAL_SOURCES
from .normalize import NormalizedInternalCompany

Normalized = Dict[str, Any]
Raw = Dict[str, Any]


def run(trigger: Normalized) -> Normalized:
    result: Normalized = {
        "source": "internal_company_research",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": {},
    }
    for source in INTERNAL_SOURCES:
        payload = source.run(trigger).get("payload", {})
        if isinstance(payload, dict):
            result["payload"].update(payload)

    try:
        validated = NormalizedInternalCompany(**result)
    except ValueError as exc:
        # Keine E-Mail hier; nur Task + sauberer Rückkanal, Wrapper übernimmt Kommunikation
        missing_fields = list(_parse_missing_fields(str(exc)))
        employee_email = _extract_email(trigger.get("recipient"))
        task = create_task("internal_company_research", missing_fields, employee_email)
        from integrations import email_sender
        email_sender.request_missing_fields(task, missing_fields, employee_email)
        final_result = {
            "source": result["source"],
            "creator": result.get("creator"),
            "recipient": result.get("recipient"),
            "payload": {
                "summary": "awaiting employee response",
                "task_id": task["id"],
                # Meta-Felder bewusst leer, damit Wrapper korrekt entscheidet
                "exists": None,
                "company_id": None,
                "last_report_date": None,
                "last_report_id": None,
                "neighbors": [],
            },
        }
        if ENABLE_GRAPH_STORAGE:
            graph_storage.store_result(final_result)
        return final_result

    final_result = asdict(validated)
    if ENABLE_GRAPH_STORAGE:
        graph_storage.store_result(final_result)
    return final_result


def _parse_missing_fields(message: str) -> Iterable[str]:
    if "Missing mandatory fields:" in message:
        return [f.strip() for f in message.split(":", 1)[1].split(",")]
    if "Missing mandatory payload field:" in message:
        return [message.split(":", 1)[1].strip()]
    return [message]


def _extract_email(recipient: Any) -> str:
    if isinstance(recipient, dict):
        return recipient.get("email", "")
    if isinstance(recipient, str):
        return recipient
    return ""
