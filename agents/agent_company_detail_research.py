"""Enrich company information with static details.

This agent performs a lightweight "detail research" step by looking up
company information from a static mapping defined in
:mod:`agents.company_data`.  In the absence of external APIs or web
scraping this provides a deterministic, reproducible data source.  The
returned payload contains core fields such as ``company_name``,
``company_domain``, ``industry``, ``classification_number``,
``description`` and ``website``.  A JSON artefact is also emitted into
the ``artifacts/`` folder for downstream use.  Should ``report_path``
and ``company_id`` be present in the incoming trigger payload the
resulting PDF will be attached to the HubSpot company via
``hubspot_api.attach_pdf``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from integrations import hubspot_api
from . import company_data

Normalized = Dict[str, Any]


def _write_artifact(filename: str, data: Any) -> None:
    """Write ``data`` as JSON into the ``artifacts`` directory.

    The directory is created if missing.  Errors during writing are
    swallowed intentionally because downstream steps should not fail
    solely due to logging problems.  The file is encoded as UTF‑8 and
    formatted with indentation.
    """
    try:
        out_dir = Path("artifacts")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / filename
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        # Best effort; avoid hard failures on IO
        pass


def run(trigger: Normalized) -> Normalized:
    """Populate detailed company information based on a static mapping.

    Parameters
    ----------
    trigger:
        Normalized trigger dictionary containing at least ``payload`` and
        ``company``/``company_name`` fields.

    Returns
    -------
    Normalized
        Dictionary with ``source``, ``creator``, ``recipient`` and a
        ``payload`` containing detailed company information.  A JSON
        artefact is persisted into ``artifacts/`` for caching.
    """
    payload = trigger.get("payload", {}) or {}
    # Pass through any pending PDF attachments to HubSpot
    report_path = payload.get("report_path")
    company_id = payload.get("company_id")
    if report_path and company_id:
        try:
            hubspot_api.attach_pdf(Path(report_path), company_id)
        except Exception:
            # Ignore HubSpot errors; this agent focuses on data enrichment
            pass

    # Derive a company name from various possible keys
    company_name = (
        payload.get("company")
        or payload.get("company_name")
        or payload.get("name")
        or ""
    )
    info = company_data.lookup_company(company_name)
    # Build a generic fallback when unknown
    if info is None:
        # Try to derive domain from payload; if missing, normalise name to
        # a DNS‑like label.  The fallback deliberately omits customers
        # and neighbours – those will be empty lists.
        domain = payload.get("domain") or payload.get("company_domain")
        if not domain:
            key = company_name.strip().lower().replace(" ", "-") or "unknown"
            domain = f"{key}.example"
        website = payload.get("website") or f"https://{domain}"
        industry = payload.get("industry") or "consulting"
        classification_number = payload.get("classification_number") or "70.22"
        description = (
            f"{company_name or 'The company'} operates in the {industry} sector. "
            f"This is a generic fallback description when no detailed information "
            f"is available in the static mapping."
        )
        info_dict = {
            "company_name": company_name or "Unknown",
            "company_domain": domain,
            "website": website,
            "industry": industry,
            "classification_number": classification_number,
            "description": description,
        }
    else:
        info_dict = {
            "company_name": info.company_name,
            "company_domain": info.company_domain,
            "website": info.website,
            "industry": info.industry,
            "classification_number": info.classification_number,
            "description": info.description,
        }

    # Persist artefact for reuse in later agents
    filename = (
        f"new_company_search_{info_dict['company_domain'].replace('.', '_')}.json"
    )
    _write_artifact(filename, info_dict)

    return {
        "source": "company_detail_research",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": info_dict,
    }