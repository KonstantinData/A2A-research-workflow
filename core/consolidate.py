# core/consolidate.py
"""Consolidation logic for merging agent outputs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable

from . import classify

Normalized = Dict[str, Any]


def consolidate(results: Iterable[Normalized]) -> Dict[str, Any]:
    """Merge agent outputs into a flat structure and annotate sources."""

    now = datetime.now(timezone.utc).isoformat()
    combined: Dict[str, Any] = {"meta": {}}

    for res in results or []:
        source = res.get("source") or "unknown"
        payload = res.get("payload") or {}
        for key, value in payload.items():
            if key not in combined or not combined.get(key):
                combined[key] = value
                combined["meta"][key] = {
                    "source": source,
                    "last_verified_at": now,
                }

    classification = classify.classify(combined)
    if classification:
        combined["classification"] = classification

    combined["creator"] = combined.get("creator") or None
    combined["recipient"] = combined.get("recipient") or None
    return combined


__all__ = ["consolidate"]

