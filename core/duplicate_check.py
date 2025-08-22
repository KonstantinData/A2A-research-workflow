# core/duplicate_check.py
"""Very small duplicate check helper."""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


def _extract_name(rec: Dict[str, Any]) -> Optional[str]:
    payload = rec.get("payload") or {}
    return rec.get("name") or payload.get("company_name") or payload.get("name")


def _extract_website(rec: Dict[str, Any]) -> Optional[str]:
    payload = rec.get("payload") or {}
    return (
        rec.get("website")
        or rec.get("domain")
        or payload.get("website")
        or payload.get("domain")
    )


def is_duplicate(
    record: Dict[str, Any], existing: Iterable[Dict[str, Any]] | None
) -> bool:
    if not existing:
        return False
    name = (_extract_name(record) or "").lower()
    website = (_extract_website(record) or "").lower()
    for r in existing:
        rn = (_extract_name(r) or "").lower()
        rw = (_extract_website(r) or "").lower()
        if name and rn and name == rn:
            return True
        if website and rw and website == rw:
            return True
    return False
