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

import importlib.util as _ilu
from datetime import datetime, timezone

from config.settings import SETTINGS

_JSONL_PATH = Path(__file__).resolve().parent.parent / "a2a_logging" / "jsonl_sink.py"
_spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
append_jsonl = _mod.append

Normalized = Dict[str, Any]


def _write_artifact(filename: str, data: Any) -> None:
    try:
        out_dir = SETTINGS.artifacts_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / filename).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _log_workflow(record: Dict[str, Any]) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    path = SETTINGS.workflows_dir / f"{ts}_workflow.jsonl"
    data = dict(record)
    data.setdefault(
        "timestamp", datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    SETTINGS.workflows_dir.mkdir(parents=True, exist_ok=True)
    append_jsonl(path, data)


def run(trigger: Normalized) -> Normalized:
    """Return potential internal customers.

    The list is derived from the static mapping and may overlap with
    external customers.  Unknown companies yield an empty list.
    """
    payload = trigger.get("payload", {}) or {}
    if payload.get("action") == "AWAIT_REQUESTOR_DECISION":
        return {"source": "internal_level2_company_search", "creator": trigger.get("creator"), "recipient": trigger.get("recipient"), "payload": {}}

    candidates = payload.get("neighbor_level2") or []
    enriched: List[Dict[str, Any]] = []
    for c in candidates:
        name = c.get("company_name")
        info = company_data.lookup_company(name) if name else None
        entry = dict(c)
        if info:
            entry.setdefault("domain", info.company_domain)
            if getattr(info, "classification", None):
                entry.setdefault("classification", dict(info.classification))
        enriched.append(entry)
    _write_artifact("internal_customer_companies.json", enriched)
    if enriched:
        _log_workflow(
            {
                "event_id": payload.get("event_id"),
                "status": "neighbor_level2_found",
                "details": {"companies": enriched},
            }
        )
    return {
        "source": "internal_level2_company_search",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": {"neighbor_level2": enriched},
    }
