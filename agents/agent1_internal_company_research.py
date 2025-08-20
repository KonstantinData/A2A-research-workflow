"""Agent 1 - internal company research."""

from __future__ import annotations

from typing import Any, Dict


Normalized = Dict[str, Any]


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
    return {
        "source": "internal_company_research",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": {
            "summary": "No internal company research available."
        },
    }
