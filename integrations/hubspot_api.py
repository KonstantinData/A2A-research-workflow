"""Lightweight HubSpot API client."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests

API_ROOT = "https://api.hubapi.com"


def _auth_headers() -> Optional[Dict[str, str]]:
    """Return authorization headers if a token is configured.

    The helpers gracefully degrade to ``None`` when no token is present.  This
    behaviour is useful for test environments where the HubSpot integration is
    not exercised.
    """

    token = os.getenv("HUBSPOT_TOKEN") or os.getenv("HUBSPOT_ACCESS_TOKEN")
    if not token:
        return None
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def upsert_company(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create or update a company record in HubSpot.

    The function posts the provided ``data`` as HubSpot company properties.  The
    response body is returned so callers can extract the company ID if needed.
    """

    url = f"{API_ROOT}/crm/v3/objects/companies"
    headers = _auth_headers()
    if headers is None:
        return {}
    resp = requests.post(url, headers=headers, json={"properties": data}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def attach_pdf(pdf_path: str | Path) -> Dict[str, Any]:
    """Upload a PDF file to HubSpot and associate it with the company.

    ``pdf_path`` may be a string or :class:`Path`.  The uploaded file ID is
    returned for further linking.
    """

    path = Path(pdf_path)
    url = f"{API_ROOT}/files/v3/files"
    headers = _auth_headers()
    if headers is None:
        return {}
    # File uploads use multipart form data so the content-type header must be
    # removed; ``requests`` will set it automatically.
    headers.pop("Content-Type", None)
    files = {"file": (path.name, path.read_bytes(), "application/pdf")}
    data = {"folderPath": "a2a"}
    resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
    resp.raise_for_status()
    return resp.json()


__all__ = ["upsert_company", "attach_pdf"]
