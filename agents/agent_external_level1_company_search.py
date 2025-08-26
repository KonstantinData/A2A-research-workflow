"""External level 1 company search.

This agent proposes companies operating in a similar space to the
organisation named in the trigger.  It uses the static mapping
defined in :mod:`agents.company_data` to look up neighbour companies
and returns a list of suggestions.  The purpose of this step is to
provide additional research targets for further enrichment and to
avoid redundant work.

In the refactored data model the returned neighbour entries surface
``industry_group``, ``industry`` and ``description``.  A
``classification`` mapping is included only when available for
backwards compatibility.  A JSON artefact is written into the
``artifacts/`` directory so subsequent steps (or external tools) may
reuse the neighbour list.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from . import company_data

Normalized = Dict[str, Any]


def _write_artifact(filename: str, data: Any) -> None:
    """Persist ``data`` as JSON in the ``artifacts`` folder.

    Creation of the folder is attempted if it does not exist.  Errors
    are ignored to ensure the pipeline is resilient to file system
    problems.
    """
    try:
        out_dir = Path("artifacts")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / filename).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def run(trigger: Normalized) -> Normalized:
    """Return a list of neighbouring companies.

    Parameters
    ----------
    trigger:
        Normalized trigger dictionary.  The company name is taken from
        ``payload['company']`` or ``payload['company_name']``.

    Returns
    -------
    Normalized
        Dictionary with ``source``, ``creator`` and ``recipient`` keys and a
        ``payload`` containing a ``companies`` list.  Each element in
        ``companies`` is a dictionary with keys ``company_name``,
        ``company_domain``, ``industry_group``, ``industry`` and
        ``description``.  A ``classification`` mapping is present only
        when provided in the static dataset.
    """
    payload = trigger.get("payload", {}) or {}
    company_name = (
        payload.get("company")
        or payload.get("company_name")
        or payload.get("name")
        or ""
    )
    neighbours: List[Dict[str, Any]] = []
    # Suggest up to five neighbour companies in the same sector.  Slice
    # the result for clarity but allow fewer entries when less are available.
    for info in company_data.neighbours_for(company_name)[:5]:
        entry: Dict[str, Any] = {
            "company_name": info.company_name,
            "company_domain": info.company_domain,
            "industry_group": info.industry_group,
            "industry": info.industry,
            "description": info.description,
        }
        if getattr(info, "classification", None):
            entry["classification"] = dict(info.classification)
        neighbours.append(entry)
    # Emit artefact for downstream consumption
    _write_artifact("neighbor_level1_companies.json", neighbours)
    return {
        "source": "company_search",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": {
            "companies": neighbours,
        },
    }