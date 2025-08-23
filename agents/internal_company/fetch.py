"""Data retrieval for internal company research."""

from __future__ import annotations

from typing import Any, Dict

Normalized = Dict[str, Any]
Raw = Dict[str, Any]


def fetch(trigger: Normalized) -> Raw:
    """Fetch raw internal company data.

    Parameters
    ----------
    trigger:
        Normalized trigger dictionary passed from the orchestrator.

    Returns
    -------
    Raw
        Unstructured data retrieved from internal systems.
    """
    return {"summary": "No internal company research available."}
