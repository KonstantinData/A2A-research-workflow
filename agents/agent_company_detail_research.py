"""Enrich company information with static details.

This agent performs a lightweight detail research step by looking up
company information from a static mapping defined in
``agents.company_data``.  The data model has been refactored to
eliminate mandatory classification numbers.  Instead each company
record surfaces an ``industry_group``, an ``industry`` and a
free‑form ``description``.  Classification codes are retained only in
the optional ``classification`` mapping for backward compatibility.

When a company is unknown in the static mapping a generic fallback is
built from the trigger payload.  The fallback derives a plausible
domain and website and uses simple heuristics to assign an industry
group from the provided industry.  A JSON artefact is emitted into
the ``artifacts/`` directory for downstream reuse.

Should ``report_path`` and ``company_id`` be present in the incoming
trigger payload the resulting PDF will be attached to the HubSpot
company via ``hubspot_api.attach_pdf``.
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
        Normalized trigger dictionary containing at least a ``payload``.

    Returns
    -------
    Normalized
        Dictionary with ``source``, ``creator`` and ``recipient`` keys and
        a ``payload`` containing enriched company information.  A JSON
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
    # Build a generic fallback when unknown.  Assign an industry group
    # based on the provided or default industry.  Unknown values default
    # to "Other".  No neighbours or customers are included in the fallback.
    if info is None:
        domain = payload.get("domain") or payload.get("company_domain")
        if not domain:
            key = company_name.strip().lower().replace(" ", "-") or "unknown"
            domain = f"{key}.example"
        website = payload.get("website") or f"https://{domain}"
        industry = payload.get("industry") or "consulting"
        # Map basic industries into high level groups.  Unknown values
        # default to "Other".  Use lower case for matching.
        _group_map = {
            "manufacturing": "Manufacturing",
            "technology": "Technology",
            "software": "Technology",
            "consulting": "Services",
            "retail": "Services",
            "pharmaceuticals": "Healthcare",
            "healthcare": "Healthcare",
            "finance": "Finance",
            "agriculture": "Agriculture",
        }
        industry_group = _group_map.get(industry.lower(), "Other")
        description = (
            f"{company_name or 'The company'} operates in the {industry} sector. "
            f"This is a generic fallback description when no detailed information "
            f"is available in the static mapping."
        )
        info_dict = {
            "company_name": company_name or "Unknown",
            "company_domain": domain,
            "website": website,
            "industry_group": industry_group,
            "industry": industry,
            "description": description,
        }
    else:
        info_dict = {
            "company_name": info.company_name,
            "company_domain": info.company_domain,
            "website": info.website,
            "industry_group": info.industry_group,
            "industry": info.industry,
            "description": info.description,
        }
        # Include classification mapping when available to preserve backward
        # compatibility.  The caller may ignore this field.
        if getattr(info, "classification", None):
            info_dict["classification"] = dict(info.classification)
    # Use core.classify to infer classification codes from the description if no
    # explicit mapping exists.  This yields a dictionary keyed by scheme.
    try:
        from core import classify as _classify
        if "classification" not in info_dict:
            cls = _classify.classify(info_dict)
            if cls:
                info_dict["classification"] = cls
    except Exception:
        pass

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