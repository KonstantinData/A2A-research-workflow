"""Internal level 2 company/customer research.

This agent proposes potential internal customers or related organisations
within the company's own ecosystem.  For the scope of this project it
reuses the static mapping from :mod:`agents.company_data`.  In a real
deployment this function would connect to a CRM or internal data
warehouse to identify opportunities based on invoices, open deals or
support tickets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from . import company_data

Normalized = Dict[str, Any]


def _write_artifact(filename: str, data: Any) -> None:
    try:
        out_dir = Path("artifacts")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / filename).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def run(trigger: Normalized) -> Normalized:
    """Return potential internal customers.

    The list is derived from the static mapping and may overlap with
    external customers.  Unknown companies yield an empty list.
    """
    payload = trigger.get("payload", {}) or {}
    company_name = (
        payload.get("company")
        or payload.get("company_name")
        or payload.get("name")
        or ""
    )
    customers: List[str] = company_data.customers_for(company_name)
    # Persist to artefact
    _write_artifact("internal_customer_companies.json", customers)
    return {
        "source": "internal_customer_research",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": {
            "customers": customers,
        },
    }