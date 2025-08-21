"""Duplicate detection module with fuzzy matching."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, Iterable

Record = Dict[str, Any]


def is_duplicate(record: Record, candidates: Iterable[Record] | None = None, *, threshold: float = 0.9) -> bool:
    """Return ``True`` if ``record`` matches any of the ``candidates``.

    Parameters
    ----------
    record:
        The record to check.  A ``name`` field is looked up and compared.
    candidates:
        Iterable of existing records against which to compare.  Only the ``name``
        field is considered.  If ``None`` (default) no duplicates are detected.
    threshold:
        Similarity ratio above which two names are considered identical.  The
        default of ``0.9`` is a conservative fuzzy match.
    """

    name = (record.get("name") or "").strip().lower()
    if not name:
        return False

    candidates = candidates or []
    for existing in candidates:
        other = (existing.get("name") or "").strip().lower()
        if not other:
            continue
        ratio = SequenceMatcher(None, name, other).ratio()
        if ratio >= threshold:
            return True
    return False


__all__ = ["is_duplicate"]
