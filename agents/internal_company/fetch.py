"""Data retrieval for internal company research."""

from __future__ import annotations

import time
from typing import Any, Dict, Tuple

Normalized = Dict[str, Any]
Raw = Dict[str, Any]

# Simple in-memory cache keyed by company identifier
_CACHE: Dict[str, Tuple[float, Raw]] = {}

# Default time-to-live for cached CRM responses (in seconds)
CACHE_TTL_SECONDS = 3600


def _retrieve_from_crm(company: str) -> Raw:
    """Placeholder CRM lookup.

    In the real system this would query an internal CRM for details
    about ``company``.  For the purposes of the example repository we
    simply return the same stubbed payload that was previously
    returned by :func:`fetch`.
    """

    return {"summary": "No internal company research available."}


def fetch(trigger: Normalized, force_refresh: bool = False) -> Raw:
    """Fetch raw internal company data.

    Parameters
    ----------
    trigger:
        Normalized trigger dictionary passed from the orchestrator.
    force_refresh:
        Bypass the cache and force a fresh CRM lookup when ``True``.

    Returns
    -------
    Raw
        Unstructured data retrieved from internal systems.
    """
    payload = trigger.get("payload") or {}
    company = payload.get("company")

    if not company:
        return {"summary": "No internal company research available."}

    now = time.time()
    cached = _CACHE.get(company)
    if not force_refresh and cached and cached[0] > now:
        return cached[1]

    raw = _retrieve_from_crm(company)
    _CACHE[company] = (now + CACHE_TTL_SECONDS, raw)
    return raw
