# integrations/hubspot_api.py
"""Minimal HubSpot CRM integration (best-effort)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import json
import requests


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
    """Return latest report file for ``company_id`` if present."""
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
