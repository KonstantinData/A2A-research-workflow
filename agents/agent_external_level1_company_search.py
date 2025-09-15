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

import importlib.util as _ilu
from datetime import datetime, timezone

_JSONL_PATH = Path(__file__).resolve().parent.parent / "a2a_logging" / "jsonl_sink.py"
_spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
append_jsonl = _mod.append

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


def _log_workflow(record: Dict[str, Any]) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    path = Path("logs") / "workflows" / f"{ts}_workflow.jsonl"
    data = dict(record)
    data.setdefault(
        "timestamp", datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    append_jsonl(path, data)


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
    if payload.get("action") == "AWAIT_REQUESTOR_DECISION":
        return {"source": "company_search", "creator": trigger.get("creator"), "recipient": trigger.get("recipient"), "payload": {}}

    company_name = (
        payload.get("company")
        or payload.get("company_name")
        or payload.get("name")
        or ""
    )
    samples = payload.get("level1_samples") or []
    neighbours: List[Dict[str, Any]] = []
    names = [company_name] + [s.get("company_name") for s in samples if s.get("company_name")]
    for name in names:
        for info in company_data.neighbours_for(name)[:5]:
            entry: Dict[str, Any] = {
                "company_name": info.company_name,
                "domain": info.company_domain,
                "classification": getattr(info, "classification", None) or "n/v",
                "reason_for_match": "same product line / compatible component",
            }
            neighbours.append(entry)
    _write_artifact("neighbor_level1_companies.json", neighbours)
    if neighbours:
        _log_workflow(
            {
                "event_id": payload.get("event_id"),
                "status": "neighbor_level1_found",
                "details": {"companies": neighbours},
            }
        )
    return {
        "source": "company_search",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": {"neighbor_level1": neighbours},
    }