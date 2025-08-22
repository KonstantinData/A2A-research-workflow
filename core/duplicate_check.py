# core/duplicate_check.py
"""Very small duplicate check helper."""
from __future__ import annotations

from typing import Any, Dict, Iterable


def is_duplicate(
    record: Dict[str, Any], existing: Iterable[Dict[str, Any]] | None
) -> bool:
    if not existing:
        return False
    name = (record.get("payload") or {}).get("company_name") or (
        record.get("payload") or {}
    ).get("name")
    website = (record.get("payload") or {}).get("website") or (
        record.get("payload") or {}
    ).get("domain")
    for r in existing:
        rn = (r.get("payload") or {}).get("company_name") or (
            r.get("payload") or {}
        ).get("name")
        rw = (r.get("payload") or {}).get("website") or (r.get("payload") or {}).get(
            "domain"
        )
        if (name and rn and name.lower() == rn.lower()) or (
            website and rw and website.lower() == rw.lower()
        ):
            return True
    return False
