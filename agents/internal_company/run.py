"""Orchestrate internal company research fetch and normalize."""

from __future__ import annotations

from typing import Any, Dict

from . import fetch, normalize

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
    raw: Raw = fetch.fetch(trigger)
    return normalize.normalize(trigger, raw)
