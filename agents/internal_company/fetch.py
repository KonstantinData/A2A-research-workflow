# agents/internal_company/fetch.py
"""Data retrieval for internal company research (LIVE via HubSpot)."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Tuple, Optional, List

from integrations import hubspot_api  # erwartet: echte Implementierung

# Import the static company dataset.  The internal company search
# should not rely on HubSpot’s search API.  Instead we look up
# companies directly in our own dataset.  The hubspot_api module
# exposes ``lookup_company`` and ``all_company_names`` when the
# agents package is available.  If the import fails the variables
# below will be ``None`` which simply results in no static match.
try:
    # pylint: disable=unused-import
    from agents.company_data import lookup_company as _lookup_company  # type: ignore
    from agents.company_data import all_company_names as _all_company_names  # type: ignore
except Exception:
    _lookup_company = None  # type: ignore
    _all_company_names = lambda: []  # type: ignore

Normalized = Dict[str, Any]
Raw = Dict[str, Any]

# Simple in-memory cache keyed by company_domain (fallback: company_name)
_CACHE: Dict[str, Tuple[float, Raw]] = {}
CACHE_TTL_SECONDS = int(os.getenv("INTERNAL_FETCH_CACHE_TTL", "3600"))


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
    """
    Search for a company in the static in‑memory dataset.

    According to the project requirements, the internal company lookup must
    not query HubSpot for companies.  Instead this helper inspects the
    static dataset defined in :mod:`agents.company_data`.  The lookup
    first tries to match the domain against the ``company_domain`` field
    of each known company.  If no domain match is found it falls back
    to a case‑insensitive name match.  If a company is located the
    returned dictionary mimics a minimal HubSpot company object with
    ``id`` and ``properties`` keys.  When no match is available an
    empty dictionary is returned.

    Parameters
    ----------
    name: str
        The company name to search for.
    domain: str
        The company domain (lowercase) to search for.

    Returns
    -------
    Dict[str, Any]
        A minimal record representing the company if found, otherwise
        an empty dictionary.
    """
    # Prefer domain match when provided
    if domain and _lookup_company and _all_company_names:
        for comp_name in _all_company_names():
            ci = _lookup_company(comp_name)
            if ci and ci.company_domain.lower() == domain.strip().lower():
                return {
                    "id": f"static-{ci.company_domain}",
                    "properties": {"name": ci.company_name, "domain": ci.company_domain},
                }
    # Fall back to name match
    if name and _lookup_company:
        ci = _lookup_company(name)
        if ci:
            return {
                "id": f"static-{ci.company_domain}",
                "properties": {"name": ci.company_name, "domain": ci.company_domain},
            }
    # Nothing found
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
    classification: Optional[str], industry: Optional[str], description: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Zusätzliche CRM-Nachbarn für L1/L2-Suche bereitstellen.
    Erwartet:
      - find_similar_companies(classification, industry, description) -> iterable
    """
    if not (classification or industry or description):
        return []
    rows = []
    for c in (
        hubspot_api.find_similar_companies(classification, industry, description) or []
    ):
        # mind. 2 Pflichtfelder
        fields = {
            "company_name": c.get("company_name") or c.get("name"),
            "company_domain": c.get("company_domain") or c.get("domain"),
            "industry": c.get("industry"),
            "classification_number": c.get("classification_number")
            or c.get("nace")
            or c.get("sic"),
            "source": "crm",
            "confidence": float(c.get("confidence", 0.0)),
        }
        present = sum(
            1
            for k in (
                "company_name",
                "company_domain",
                "industry",
                "classification_number",
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
                payload.get("classification_number"),
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
        "last_report_date": last_date,  # ISO-8601 erwartet von hubspot_api
        "last_report_id": last_id,
        "neighbors": _neighbors(
            payload.get("classification_number"),
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

    cached = _CACHE.get(cache_key)
    if not force_refresh and cached and cached[0] > now:
        return cached[1]

    raw = _retrieve_from_crm(payload)
    _CACHE[cache_key] = (now + CACHE_TTL_SECONDS, raw)
    return raw
