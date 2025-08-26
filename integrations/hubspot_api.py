# integrations/hubspot_api.py
"""Minimal HubSpot CRM integration (best-effort)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import json
import requests

# The static company data is used as a lightweight substitute for a real
# CRM or HubSpot look‑up.  In the live system these helpers would
# perform authenticated API calls to HubSpot to locate companies by
# domain or name, retrieve associated reports and discover similar
# organisations.  For the purposes of unit testing and running the
# full workflow without external connectivity the functions below
# consult the in‑memory dataset defined in ``agents/company_data``.
try:
    # Import at runtime to avoid circular dependencies when this module
    # is imported during testing.  The import may fail if the agents
    # package is not available; in that case the helper functions
    # simply return None or empty lists.
    from agents.company_data import lookup_company, all_company_names, CompanyInfo  # type: ignore
except Exception:
    lookup_company = None  # type: ignore
    all_company_names = lambda: []  # type: ignore
    CompanyInfo = None  # type: ignore


def _token() -> Optional[str]:
    return os.getenv("HUBSPOT_ACCESS_TOKEN")


def upsert_company(data: Dict[str, Any]) -> None:
    """Create or update a company in HubSpot (best-effort)."""
    token = _token()
    if not token:
        # No token provided – skip silently.
        return

    props = {}
    payload = data.get("payload") or {}
    # Try to map a few common fields if present
    props["name"] = payload.get("company_name") or payload.get("name") or "Unknown"
    website = payload.get("website") or payload.get("domain")
    if website:
        props["domain"] = website

    url = "https://api.hubapi.com/crm/v3/objects/companies"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        requests.post(
            url, headers=headers, data=json.dumps({"properties": props}), timeout=10
        )
    except Exception:
        # Do not fail the pipeline on HubSpot errors
        pass


def check_existing_report(company_id: str) -> Optional[Dict[str, Any]]:
    """Return latest report (id, name, createdAt) for ``company_id`` if present."""
    token = _token()
    if not token:
        return None

    url = "https://api.hubapi.com/files/v3/files/search"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "filters": [
            {"propertyName": "name", "operator": "CONTAINS_TOKEN", "value": "report"},
            {"propertyName": "companyId", "operator": "EQ", "value": company_id},
        ],
        "limit": 1,
        "sorts": ["-createdAt"],
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0] if results else None


def attach_pdf(path: Path, company_id: str) -> Dict[str, str]:
    """Upload ``path`` to HubSpot and associate with a company."""
    token = _token()
    portal_id = os.getenv("HUBSPOT_PORTAL_ID")
    if not token or not portal_id:
        raise RuntimeError("missing HubSpot credentials")

    headers = {"Authorization": f"Bearer {token}"}
    upload_url = "https://api.hubapi.com/files/v3/files"
    data = {"options": json.dumps({"access": "PRIVATE"})}
    with path.open("rb") as fh:
        files = {"file": (path.name, fh, "application/pdf")}
        resp = requests.post(upload_url, headers=headers, files=files, data=data, timeout=10)
    resp.raise_for_status()
    file_id = resp.json().get("id")

    assoc_url = (
        f"https://api.hubapi.com/crm/v3/objects/companies/{company_id}/associations/files/{file_id}"
    )
    assoc_payload = {"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 112}
    resp2 = requests.put(assoc_url, headers=headers, json=assoc_payload, timeout=10)
    resp2.raise_for_status()
    assoc_id = resp2.json().get("id", "")

    return {"file_id": file_id, "association_id": assoc_id}


# --- Static lookup helpers -------------------------------------------------

def _build_company_record(info: "CompanyInfo", *, domain_only: bool = False) -> Dict[str, Any]:
    """Return a simplified HubSpot company record for a given CompanyInfo.

    Parameters
    ----------
    info: CompanyInfo
        The static company information to convert.
    domain_only: bool, default False
        When True only return the record if the caller supplied a
        matching domain.  When False the record is always returned.

    Returns
    -------
    Dict[str, Any]
        A dictionary emulating the shape of HubSpot's company object.
    """
    # Use a synthetic ID to mimic HubSpot's internal identifier.  In a
    # real implementation the ID would be returned by the API.
    record_id = f"static-{info.company_domain}"
    props = {
        "name": info.company_name,
        "domain": info.company_domain,
    }
    # Include an updatedAt timestamp to aid sorting by recency.  When
    # working offline we cannot know when the data was last updated, so
    # omit the field.  Tests that sort by updatedAt should handle
    # missing values gracefully.
    record: Dict[str, Any] = {
        "id": record_id,
        "properties": props,
    }
    return record


def find_company_by_domain(domain: str) -> Optional[Dict[str, Any]]:
    """Return a HubSpot‑like company record matching ``domain``.

    The lookup uses the in‑memory static dataset defined in
    :mod:`agents.company_data`.  If no match is found or the data
    module is unavailable the function returns ``None``.

    Parameters
    ----------
    domain: str
        The domain to search for.  Comparison is case insensitive.

    Returns
    -------
    Optional[Dict[str, Any]]
        A dictionary containing ``id`` and ``properties`` keys if a
        match is found, otherwise ``None``.
    """
    if not domain:
        return None
    if lookup_company is None:
        return None
    # Iterate over all companies and compare the domain case
    # insensitively.  We avoid building the entire dataset into a
    # mapping keyed by domain to keep the static helper simple.
    for name in all_company_names():
        ci = lookup_company(name)
        if ci and ci.company_domain.lower() == domain.strip().lower():
            return _build_company_record(ci)
    return None


def find_company_by_name(name: str) -> List[Dict[str, Any]]:
    """Return a list of possible company matches for ``name``.

    The static dataset is searched for a case insensitive match on the
    company name.  If a match is found it is returned as a single
    element list; otherwise an empty list is returned.  In a real
    implementation this function would call the HubSpot search API.

    Parameters
    ----------
    name: str
        The company name to search for.  Comparison is case insensitive.

    Returns
    -------
    List[Dict[str, Any]]
        A list of dictionaries each representing a possible match.
    """
    if not name:
        return []
    if lookup_company is None:
        return []
    ci = lookup_company(name)
    if not ci:
        return []
    # Return a single match with an updatedAt field to satisfy sorting.
    record = _build_company_record(ci)
    # Add a dummy updatedAt timestamp; using the epoch ensures older
    # records sort before newer ones when combined with other data.
    record["updatedAt"] = "1970-01-01T00:00:00Z"
    return [record]


def list_company_reports(company_id: str) -> List[Dict[str, Any]]:
    """Return a list of previously generated reports for ``company_id``.

    Since this environment does not persist real HubSpot attachments,
    this helper returns an empty list.  In a production system the
    implementation would call ``GET /crm/v3/objects/companies/{companyId}/associations/files``
    or similar to list associated files.

    Parameters
    ----------
    company_id: str
        The identifier of the company whose reports should be listed.

    Returns
    -------
    List[Dict[str, Any]]
        A list of dictionaries describing each report.  Each element
        may contain keys such as ``id``, ``reportDate`` and
        ``createdAt``.  An empty list indicates no previous reports.
    """
    # Without a backend service we cannot know if a company has any
    # existing reports, so return an empty list.  The internal company
    # research will interpret this as no reports and therefore avoid
    # caching outdated results.
    return []


def find_similar_companies(
    classification: Optional[str], industry: Optional[str], description: Optional[str]
) -> List[Dict[str, Any]]:
    """Suggest companies with similar characteristics.

    This helper scans the static dataset for companies that share the
    same classification number or industry.  If no criteria are
    provided an empty list is returned.  Each suggestion includes
    ``company_name``, ``company_domain``, ``industry``, ``classification_number``
    and a confidence score.  The score is a simple heuristic based on
    how many attributes match; it ranges from 0.0 to 1.0.

    Parameters
    ----------
    classification: Optional[str]
        The classification number to match against.
    industry: Optional[str]
        The industry description to match against.
    description: Optional[str]
        A free text description (unused in this static implementation).

    Returns
    -------
    List[Dict[str, Any]]
        A list of candidate companies with associated data and confidence
        scores.  An empty list is returned if no criteria are provided
        or if the static dataset is unavailable.
    """
    if lookup_company is None:
        return []
    if not (classification or industry or description):
        return []
    suggestions: List[Dict[str, Any]] = []
    for name in all_company_names():
        ci = lookup_company(name)
        if not ci:
            continue
        matches = 0
        total = 0
        # Compare classification number if provided
        if classification:
            total += 1
            if ci.classification_number == classification:
                matches += 1
        # Compare industry if provided
        if industry:
            total += 1
            if ci.industry.lower() == industry.lower():
                matches += 1
        # Description could be compared via text similarity; omitted
        # here due to complexity.  In a real implementation this would
        # contribute to the confidence.
        if total == 0:
            continue
        confidence = matches / total if total else 0.0
        suggestions.append(
            {
                "company_name": ci.company_name,
                "company_domain": ci.company_domain,
                "industry": ci.industry,
                "classification_number": ci.classification_number,
                "confidence": confidence,
            }
        )
    return suggestions
