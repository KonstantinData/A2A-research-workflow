# agents/internal_company/fetch.py
"""Data retrieval for internal company research (LIVE via HubSpot)."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Tuple, Optional, List

from integrations import hubspot_api  # erwartet: echte Implementierung
from config.settings import SETTINGS

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None  # type: ignore


def _empty_names() -> List[str]:
    return []

# Optional static dataset for tests only
if SETTINGS.allow_static_company_data:
    try:
        from agents.company_data import lookup_company as _lookup_company  # type: ignore
        from agents.company_data import all_company_names as _all_company_names  # type: ignore
    except Exception:  # pragma: no cover - dataset not available
        _lookup_company = None  # type: ignore
        _all_company_names = _empty_names  # type: ignore
else:
    _lookup_company = None  # type: ignore
    _all_company_names = _empty_names  # type: ignore

Normalized = Dict[str, Any]
Raw = Dict[str, Any]

# Simple in-memory cache keyed by company_domain (fallback: company_name)
_CACHE: Dict[str, Tuple[float, Raw]] = {}
# Domain-to-company mapping for O(1) lookups
_DOMAIN_MAPPING: Dict[str, str] = {}
_CACHE_CLIENT = None
REDIS_URL = SETTINGS.internal_fetch_redis_url
if REDIS_URL and redis is not None:
    try:
        _CACHE_CLIENT = redis.Redis.from_url(REDIS_URL)
    except Exception:  # pragma: no cover - Redis connection failed
        _CACHE_CLIENT = None
CACHE_TTL_SECONDS = int(SETTINGS.internal_fetch_cache_ttl or 0) or 3600


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _pick_company_key(payload: Dict[str, Any]) -> Tuple[str, str]:
    # Backward compatible: accept 'company' or the new pair
    name = (payload.get("company_name") or payload.get("company") or "").strip()
    domain = (payload.get("company_domain") or "").strip().lower()
    if not (name or domain):
        raise ValueError(
            "missing required fields: company_name/company_domain (or legacy 'company')"
        )
    return name, domain


def _find_company(name: str, domain: str) -> Dict[str, Any]:
    """Locate a company via HubSpot or optional static dataset."""

    try:
        if domain:
            match = hubspot_api.find_company_by_domain(domain)
            if match:
                return match
        if name:
            matches = hubspot_api.find_company_by_name(name) or []
            if matches:
                return matches[0]
    except Exception:
        if not SETTINGS.allow_static_company_data:
            raise

    if SETTINGS.allow_static_company_data and _lookup_company and _all_company_names:
        if domain:
            # Initialize domain mapping if empty
            if not _DOMAIN_MAPPING:
                for comp_name in _all_company_names():
                    ci = _lookup_company(comp_name)
                    if ci:
                        _DOMAIN_MAPPING[ci.company_domain.lower()] = comp_name
            
            # O(1) domain lookup
            comp_name = _DOMAIN_MAPPING.get(domain.strip().lower())
            if comp_name:
                ci = _lookup_company(comp_name)
                if ci:
                    return {
                        "id": f"static-{ci.company_domain}",
                        "properties": {"name": ci.company_name, "domain": ci.company_domain},
                    }
        if name:
            ci = _lookup_company(name)
            if ci:
                return {
                    "id": f"static-{ci.company_domain}",
                    "properties": {"name": ci.company_name, "domain": ci.company_domain},
                }
    return {}


def _latest_report(company_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Liefert (last_report_date_iso, last_report_id) basierend auf Attachments.
    Erwartet:
      - list_company_reports(company_id) -> List[{id, filename, createdAt, reportDate?}]
    """
    files = hubspot_api.list_company_reports(company_id) or []
    if not files:
        return None, None
    # heuristik: reportDate > createdAt > Name parsieren übernimmt hubspot_api
    files = sorted(
        files,
        key=lambda f: (f.get("reportDate") or f.get("createdAt") or ""),
        reverse=True,
    )
    f0 = files[0]
    last_dt = f0.get("reportDate") or f0.get("createdAt")
    return last_dt, f0.get("id")


def _neighbors(
    industry_group: Optional[str], industry: Optional[str], description: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Return additional CRM neighbours for level‑1/level‑2 search.

    The refactored data model no longer depends on opaque classification
    numbers.  Instead this helper uses the industry group, industry
    and free text description to discover similar companies.  The
    underlying HubSpot helper ``find_similar_companies`` accepts the
    same parameters.  At least one hint must be provided; otherwise
    an empty list is returned.
    """
    if not (industry_group or industry or description):
        return []
    rows: List[Dict[str, Any]] = []
    # Pass the industry_group as the first argument to preserve call signature;
    # older implementations may treat this argument as a classification number.
    for c in hubspot_api.find_similar_companies(industry_group, industry, description) or []:
        # build a candidate record; require at least two identifying fields
        fields = {
            "company_name": c.get("company_name") or c.get("name"),
            "company_domain": c.get("company_domain") or c.get("domain"),
            "industry_group": c.get("industry_group"),
            "industry": c.get("industry"),
            "description": c.get("description"),
            "source": "crm",
            "confidence": float(c.get("confidence", 0.0)),
        }
        present = sum(
            1
            for k in (
                "company_name",
                "company_domain",
                "industry_group",
                "industry",
            )
            if fields.get(k)
        )
        if present >= 2:
            rows.append(fields)
    return rows


def _retrieve_from_crm(payload: Dict[str, Any]) -> Raw:
    name, domain = _pick_company_key(payload)
    company = _find_company(name, domain)
    exists = bool(company)
    if not exists:
        return {
            "summary": "company not found in CRM",
            "exists": False,
            "company_id": None,
            "company_name": name,
            "company_domain": domain,
            "last_report_date": None,
            "last_report_id": None,
            "neighbors": _neighbors(
                payload.get("industry_group"),
                payload.get("industry"),
                payload.get("description"),
            ),
        }

    company_id = company.get("id")
    last_date, last_id = _latest_report(company_id)
    return {
        "summary": "company found in CRM",
        "exists": True,
        "company_id": company_id,
        "company_name": company.get("properties", {}).get("name") or name,
        "company_domain": company.get("properties", {}).get("domain") or domain,
        "last_report_date": last_date,  # ISO-8601 expected from hubspot_api
        "last_report_id": last_id,
        "neighbors": _neighbors(
            payload.get("industry_group"),
            payload.get("industry"),
            payload.get("description"),
        ),
    }


def fetch(trigger: Normalized, force_refresh: bool = False) -> Raw:
    """Fetch raw internal company data (LIVE, cached)."""
    payload = trigger.get("payload") or {}
    name, domain = _pick_company_key(payload)
    cache_key = domain or name
    now = time.time()

    if _CACHE_CLIENT:
        if not force_refresh:
            cached_bytes = _CACHE_CLIENT.get(cache_key)
            if cached_bytes:
                try:
                    return json.loads(cached_bytes)
                except Exception:
                    pass
        raw = _retrieve_from_crm(payload)
        try:
            _CACHE_CLIENT.set(cache_key, json.dumps(raw), ex=CACHE_TTL_SECONDS)
        except Exception:
            pass
        return raw

    cached = _CACHE.get(cache_key)
    if not force_refresh and cached and cached[0] > now:
        return cached[1]

    raw = _retrieve_from_crm(payload)
    _CACHE[cache_key] = (now + CACHE_TTL_SECONDS, raw)
    return raw
