"""External level 2 company/customer search.

This agent proposes potential downstream organisations (e.g. customers
or partners) for the company referenced in the trigger.  It uses the
static mapping defined in :mod:`agents.company_data` to return a list
of names.  If a company is unknown no suggestions are provided.
Results are persisted into an artefact for reuse in later stages.
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
    """Return potential downstream organisations.

    The company name is extracted from the trigger payload and looked up
    in the static dataset.  A list of customer names is returned.  If
    the company is unknown the list is empty.
    """
    payload = trigger.get("payload", {}) or {}
    company_name = (
        payload.get("company")
        or payload.get("company_name")
        or payload.get("name")
        or ""
    )
    customers: List[str] = company_data.customers_for(company_name)
    # Persist for later reuse
    _write_artifact("external_new_level2_companies.json", customers)
    return {
        "source": "external_branch_research",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": {
            "companies": customers,
        },
    }