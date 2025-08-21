"""Consolidation logic for merging agent outputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable

from . import classify

Normalized = Dict[str, Any]


def consolidate(results: Iterable[Normalized]) -> Dict[str, Any]:
    """Consolidate data from multiple agents into the core schema.

    Each element in ``results`` is expected to be a mapping containing at least
    ``source`` and ``payload`` keys. The payload is merged into a single
    structure, and ``meta`` information is recorded for every field capturing
    the originating source and when the data was consolidated.
    """

    consolidated: Dict[str, Any] = {"meta": {}}
    now = datetime.now(timezone.utc).isoformat()
    sources: list[str] = []

    for result in results:
        source = result.get("source", "unknown")
        payload = result.get("payload", {})
        if not isinstance(payload, dict):
            continue
        sources.append(source)
        for key, value in payload.items():
            consolidated[key] = value
            consolidated["meta"][key] = {
                "source": source,
                "last_verified_at": now,
            }

    consolidated["meta"]["sources"] = sources
    consolidated["meta"]["last_verified_at"] = now

    # Add classification information based on the consolidated payload.
    payload_only = {k: v for k, v in consolidated.items() if k != "meta"}
    classification = classify.classify(payload_only)
    if classification["wz2008"] or classification["gpt_tags"]:
        consolidated["classification"] = classification
        consolidated["meta"]["classification"] = {
            "source": "classifier",
            "last_verified_at": now,
        }

    return consolidated
