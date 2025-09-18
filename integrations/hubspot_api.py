# integrations/hubspot_api.py
"""Minimal HubSpot CRM integration (best-effort)."""
from __future__ import annotations

import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from core.utils import log_step
from core.circuit_breaker import with_circuit_breaker

DEFAULT_TIMEOUT = 30
HS_BASE = "https://api.hubapi.com"


@with_circuit_breaker("hubspot", failure_threshold=3, recovery_timeout=30, expected_exception=requests.RequestException)
def _request_with_retry(method: str, url: str, **kwargs: Any) -> requests.Response:
    """Perform a HubSpot API request with retry/backoff for transient failures."""

    max_retries = 3
    attempt = 0
    while True:
        try:
            response = requests.request(method, url, **kwargs)
        except requests.RequestException as exc:
            if attempt >= max_retries:
                log_step(
                    "hubspot",
                    "request_exception",
                    {
                        "method": method,
                        "url": url,
                        "error": str(exc),
                    },
                    severity="error",
                )
                raise
            sleep_for = 0.5 * (2**attempt) + random.uniform(0, 0.1)
            log_step(
                "hubspot",
                "request_retry",
                {
                    "method": method,
                    "url": url,
                    "attempt": attempt + 1,
                    "error": str(exc),
                    "backoff_seconds": round(sleep_for, 2),
                },
                severity="warning",
            )
            time.sleep(sleep_for)
            attempt += 1
            continue
        else:
            if response.status_code != 429 and not 500 <= response.status_code < 600:
                return response
            if attempt >= max_retries:
                log_step(
                    "hubspot",
                    "request_failed",
                    {
                        "method": method,
                        "url": url,
                        "status": response.status_code,
                    },
                    severity="error",
                )
                return response
            sleep_for = 0.5 * (2**attempt) + random.uniform(0, 0.1)
            log_step(
                "hubspot",
                "request_retry",
                {
                    "method": method,
                    "url": url,
                    "attempt": attempt + 1,
                    "status": response.status_code,
                    "backoff_seconds": round(sleep_for, 2),
                },
                severity="warning",
            )
            time.sleep(sleep_for)
            attempt += 1

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


def upsert_company(data: Dict[str, Any]) -> Optional[str]:
    """Create or update a company in HubSpot."""
    token = _token()
    if not token:
        live_mode = os.getenv("LIVE_MODE", "1") == "1"
        log_step(
            "hubspot",
            "missing_access_token",
            {"operation": "upsert_company", "live_mode": live_mode},
            severity="critical" if live_mode else "error",
        )
        if live_mode:
            raise RuntimeError("HUBSPOT_ACCESS_TOKEN missing in LIVE mode")
        return None
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    core = data.get("core") or data
    domain = (core.get("domain") or "").lower()

    # 1) Try lookup by domain
    if domain:
        resp = _request_with_retry(
            "post",
            f"{HS_BASE}/crm/v3/objects/companies/search",
            headers=headers,
            json={"filterGroups":[{"filters":[{"propertyName":"domain","operator":"EQ","value":domain}]}]},
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        results = (resp.json() or {}).get("results") or []
        if results:
            company_id = results[0].get("id")
            log_step(
                "hubspot",
                "company_domain_match",
                {"domain": domain, "company_id": company_id},
            )
            _update_company(company_id, core, headers)
            return company_id
        log_step(
            "hubspot",
            "company_domain_not_found",
            {"domain": domain},
        )
    # 2) Create
    company_id = _create_company(core, headers)
    return company_id


def _map_core_to_properties(core: Dict[str, Any]) -> Dict[str, Any]:
    props = {
        "name": core.get("company_name"),
        "domain": (core.get("domain") or "").lower() or None,
        "industry": core.get("industry"),
        "description": core.get("description"),
    }
    contact = core.get("contact_info") or {}
    if contact.get("email"):
        props["email"] = contact["email"]
    if contact.get("phone"):
        props["phone"] = contact["phone"]
    return {k: v for k, v in props.items() if v}


def _create_company(core: Dict[str, Any], headers: Dict[str, str]) -> Optional[str]:
    payload = {"properties": _map_core_to_properties(core)}
    try:
        resp = _request_with_retry(
            "post",
            f"{HS_BASE}/crm/v3/objects/companies",
            headers=headers,
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        log_step(
            "hubspot",
            "company_create_failed",
            {"error": str(e), "domain": payload["properties"].get("domain")},
            severity="error"
        )
        raise
    company_id = (resp.json() or {}).get("id")
    log_step(
        "hubspot",
        "company_created",
        {
            "company_id": company_id,
            "domain": payload["properties"].get("domain"),
        },
    )
    return company_id


def _update_company(company_id: str, core: Dict[str, Any], headers: Dict[str, str]) -> None:
    payload = {"properties": _map_core_to_properties(core)}
    resp = _request_with_retry(
        "patch",
        f"{HS_BASE}/crm/v3/objects/companies/{company_id}",
        headers=headers,
        json=payload,
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    log_step(
        "hubspot",
        "company_updated",
        {
            "company_id": company_id,
            "domain": payload["properties"].get("domain"),
        },
    )


def check_existing_report(company_id: str) -> Optional[Dict[str, Any]]:
    """Return latest report (id, name, createdAt) for ``company_id`` if present."""
    token = _token()
    if not token:
        live_mode = os.getenv("LIVE_MODE", "1") == "1"
        log_step(
            "hubspot",
            "missing_access_token",
            {"operation": "check_existing_report", "live_mode": live_mode},
            severity="critical" if live_mode else "error",
        )
        if live_mode:
            raise RuntimeError("HUBSPOT_ACCESS_TOKEN missing in LIVE mode")
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
    resp = _request_with_retry(
        "post",
        url,
        headers=headers,
        json=payload,
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if results:
        record = results[0]
        log_step(
            "hubspot",
            "existing_report_found",
            {
                "company_id": company_id,
                "report_id": record.get("id"),
            },
        )
        return record
    log_step(
        "hubspot",
        "existing_report_not_found",
        {"company_id": company_id},
    )
    return None


def attach_pdf(pdf_path: Path, company_id: str) -> Optional[Dict[str, Any]]:
    token = _token()
    if not token:
        live_mode = os.getenv("LIVE_MODE", "1") == "1"
        log_step(
            "hubspot",
            "missing_access_token",
            {"operation": "attach_pdf", "live_mode": live_mode},
            severity="critical" if live_mode else "error",
        )
        if live_mode:
            raise RuntimeError("HUBSPOT_ACCESS_TOKEN missing in LIVE mode")
        return None
    headers = {"Authorization": f"Bearer {token}"}
    try:
        file_content = pdf_path.read_bytes()
    except (OSError, IOError) as e:
        log_step(
            "hubspot",
            "pdf_read_failed",
            {"path": str(pdf_path), "error": str(e)},
            severity="error"
        )
        return None
    
    files = {"file": (pdf_path.name, file_content, "application/pdf")}
    data = {"folderPath": "A2A Reports"}
    up = _request_with_retry(
        "post",
        f"{HS_BASE}/files/v3/files",
        headers=headers,
        files=files,
        data=data,
        timeout=DEFAULT_TIMEOUT,
    )
    up.raise_for_status()
    file_id = (up.json() or {}).get("id")
    if not file_id:
        return None
    # Associate with company
    assoc = _request_with_retry(
        "put",
        f"{HS_BASE}/crm/v3/associations/companies/files/batch/create",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"inputs":[{"from":{"id": company_id}, "to":{"id": file_id}, "type":"company_to_file"}]},
        timeout=DEFAULT_TIMEOUT,
    )
    assoc.raise_for_status()
    log_step(
        "hubspot",
        "report_uploaded",
        {
            "company_id": company_id,
            "file_id": file_id,
            "file_name": pdf_path.name,
        },
    )
    return {"file_id": file_id}


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

    The function queries HubSpot for files associated with the given
    company via ``GET /crm/v3/objects/companies/{companyId}/associations/files``.

    Parameters
    ----------
    company_id: str
        The identifier of the company whose reports should be listed.

    Returns
    -------
    List[Dict[str, Any]]
        A list of dictionaries describing each report.  Each element
        may contain keys such as ``id`` and ``type``.  An empty list
        indicates no previous reports.
    """
    # Handle static/test company IDs - return empty list instead of making API call
    if company_id and company_id.startswith("static-"):
        log_step(
            "hubspot",
            "static_company_reports_skipped",
            {"company_id": company_id},
        )
        return []
    
    token = _token()
    if not token:
        if os.getenv("LIVE_MODE", "1") == "1":
            raise RuntimeError("HUBSPOT_ACCESS_TOKEN missing in LIVE mode")
        return []

    url = f"{HS_BASE}/crm/v3/objects/companies/{company_id}/associations/files"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = _request_with_retry(
            "get",
            url,
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network errors
        raise RuntimeError("Failed to list company reports") from exc
    return (resp.json() or {}).get("results") or []


def find_similar_companies(
    industry_group: Optional[str], industry: Optional[str], description: Optional[str]
) -> List[Dict[str, Any]]:
    """Suggest companies with similar characteristics.

    The function delegates to HubSpot's search API and maps the
    returned results into a simplified structure.  Only ``industry``
    and ``industry_group`` are used for matching; ``description`` is
    accepted for API parity but currently ignored.

    Parameters
    ----------
    industry_group: Optional[str]
        The high level industry group to match against.
    industry: Optional[str]
        The specific industry description to match against.
    description: Optional[str]
        Free text description (unused).

    Returns
    -------
    List[Dict[str, Any]]
        A list of candidate companies with associated data and a simple
        confidence score.  An empty list is returned if no criteria are
        provided or if the HubSpot token is missing in non‑LIVE mode.
    """
    token = _token()
    if not token:
        if os.getenv("LIVE_MODE", "1") == "1":
            raise RuntimeError("HUBSPOT_ACCESS_TOKEN missing in LIVE mode")
        return []

    filters: List[Dict[str, str]] = []
    if industry_group:
        filters.append({"propertyName": "industry_group", "operator": "EQ", "value": industry_group})
    if industry:
        filters.append({"propertyName": "industry", "operator": "EQ", "value": industry})
    if not filters:
        return []

    payload = {"filterGroups": [{"filters": filters}], "properties": ["name", "domain", "industry_group", "industry", "description"]}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        resp = _request_with_retry(
            "post",
            f"{HS_BASE}/crm/v3/objects/companies/search",
            headers=headers,
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network errors
        raise RuntimeError("Failed to search for similar companies") from exc

    results = (resp.json() or {}).get("results") or []
    suggestions: List[Dict[str, Any]] = []
    for item in results:
        props = item.get("properties") or {}
        matches = 0
        total = 0
        if industry_group:
            total += 1
            if (props.get("industry_group") or "").lower() == industry_group.lower():
                matches += 1
        if industry:
            total += 1
            if (props.get("industry") or "").lower() == industry.lower():
                matches += 1
        confidence = matches / total if total else 0.0
        suggestions.append(
            {
                "company_name": props.get("name"),
                "company_domain": props.get("domain"),
                "industry_group": props.get("industry_group"),
                "industry": props.get("industry"),
                "description": props.get("description"),
                "confidence": confidence,
            }
        )
    return suggestions
