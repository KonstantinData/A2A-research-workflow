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

import importlib.util as _ilu
from datetime import datetime, timezone

_JSONL_PATH = Path(__file__).resolve().parent.parent / "logging" / "jsonl_sink.py"
_spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
append_jsonl = _mod.append

Normalized = Dict[str, Any]


def _write_artifact(filename: str, data: Any) -> None:
    try:
        out_dir = Path("artifacts")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / filename).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _log_workflow(record: Dict[str, Any]) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    path = Path("logs") / "workflows" / f"{ts}_workflow.jsonl"
    data = dict(record)
    data.setdefault(
        "timestamp", datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    append_jsonl(path, data)


def run(trigger: Normalized) -> Normalized:
    """Return potential downstream organisations.

    The company name is extracted from the trigger payload and looked up
    in the static dataset.  A list of customer names is returned.  If
    the company is unknown the list is empty.
    """
    payload = trigger.get("payload", {}) or {}
    if payload.get("action") == "AWAIT_REQUESTOR_DECISION":
        return {"source": "external_branch_research", "creator": trigger.get("creator"), "recipient": trigger.get("recipient"), "payload": {}}

    level1 = payload.get("neighbor_level1") or []
    neighbours: List[Dict[str, Any]] = []
    seen = set()
    for n in level1:
        name = n.get("company_name")
        if not name:
            continue
        for cust in company_data.customers_for(name):
            if cust in seen:
                continue
            seen.add(cust)
            slug = cust.lower().replace(" ", "")
            neighbours.append(
                {
                    "company_name": cust,
                    "domain": f"{slug}.com",
                    "classification": "n/v",
                    "reason_for_match": f"uses products from Level 1 company {name}",
                }
            )
    _write_artifact("neighbor_level2_companies.json", neighbours)
    if neighbours:
        _log_workflow(
            {
                "event_id": payload.get("event_id"),
                "status": "neighbor_level2_found",
                "details": {"companies": neighbours},
            }
        )
    return {
        "source": "external_branch_research",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": {"neighbor_level2": neighbours},
    }