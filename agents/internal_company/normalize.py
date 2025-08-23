"""Schema mapping for internal company research."""

from __future__ import annotations

from typing import Any, Dict

Normalized = Dict[str, Any]
Raw = Dict[str, Any]


def normalize(trigger: Normalized, raw: Raw) -> Normalized:
    """Map raw data to the normalized schema.

    Parameters
    ----------
    trigger:
        Normalized trigger dictionary passed from the orchestrator.
    raw:
        Unstructured data retrieved by :func:`fetch`.

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
        "payload": raw,
    }
