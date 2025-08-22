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


def attach_pdf(path: Path) -> None:
    """Attach the generated PDF to a HubSpot object (no-op placeholder)."""
    # Full implementation would upload the file and associate it with a record.
    # We keep this a no-op to avoid unnecessary complexity in the example.
    return
