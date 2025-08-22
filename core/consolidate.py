# core/consolidate.py
"""Consolidation logic for merging agent outputs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from . import classify

Normalized = Dict[str, Any]


def consolidate(results: Iterable[Normalized]) -> Dict[str, Any]:
    """Consolidate data from multiple agents into a simple schema.

    The result structure:
    {
      "payload": {...},          # merged keys from agents
      "meta": {
         "sources": [...],
         "last_verified_at": "...iso..."
      }
    }
    """
    now = datetime.now(timezone.utc).isoformat()
    consolidated: Dict[str, Any] = {
        "payload": {},
        "meta": {"sources": [], "last_verified_at": now},
    }

    for res in results or []:
        source = res.get("source") or "unknown"
        consolidated["meta"]["sources"].append(source)
        payload = res.get("payload") or {}
        # merge shallow keys
        for k, v in payload.items():
            # prefer first non-empty value
            if k not in consolidated["payload"] or not consolidated["payload"][k]:
                consolidated["payload"][k] = v

    # Attach a lightweight classification based on keywords
    classification = classify.classify(consolidated["payload"])
    if classification:
        consolidated["classification"] = classification

    # bubble up creator/recipient if present
    consolidated["creator"] = consolidated["payload"].get("creator") or None
    consolidated["recipient"] = consolidated["payload"].get("recipient") or None
    return consolidated
