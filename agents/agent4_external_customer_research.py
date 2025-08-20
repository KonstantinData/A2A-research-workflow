"""Agent 4 - external customer research."""

from __future__ import annotations

from typing import Any, Dict


Normalized = Dict[str, Any]


def run(trigger: Normalized) -> Normalized:
    """Run external customer research.

    Parameters
    ----------
    trigger:
        Normalized trigger dictionary passed from the orchestrator.

    Returns
    -------
    Normalized
        Structured result with ``source``, ``creator``, ``recipient`` and
        ``payload`` keys.
    """
    return {
        "source": "external_customer_research",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": {
            "customers": [],
        },
    }
