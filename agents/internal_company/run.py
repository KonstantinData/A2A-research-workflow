"""Orchestrate internal company research fetch and normalize."""

from __future__ import annotations

from typing import Any, Dict

from .plugins import INTERNAL_SOURCES

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
    return result
