"""Orchestrate internal company research fetch and normalize."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Iterable

from core.tasks import create_task
from integrations import email_client

from .plugins import INTERNAL_SOURCES
from .normalize import NormalizedInternalCompany

Normalized = Dict[str, Any]
Raw = Dict[str, Any]


def run(trigger: Normalized) -> Normalized:
    """Run internal company research.

    Parameters
    ----------
    trigger:
        Normalized trigger dictionary passed from the orchestrator.

    Returns
    -------
    Normalized
        Structured result following the common schema of ``source``,
        ``creator``, ``recipient`` and ``payload``.
    """
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
        missing_fields = _parse_missing_fields(str(exc))
        employee_email = _extract_email(trigger.get("recipient"))
        task = create_task("internal_company_research", missing_fields, employee_email)
        email_client.send_email(employee_email, missing_fields)
        return {
            "source": result["source"],
            "creator": result.get("creator"),
            "recipient": result.get("recipient"),
            "payload": {
                "summary": "awaiting employee response",
                "task_id": task["id"],
            },
        }
    return asdict(validated)


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
