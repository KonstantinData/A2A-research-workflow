from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from core.utils import get_workflow_id
import importlib.util as _ilu
from config.settings import SETTINGS

try:
    _JSONL_PATH = Path(__file__).resolve().parents[1] / "a2a_logging" / "jsonl_sink.py"
    _spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
    _mod = _ilu.module_from_spec(_spec)
    assert _spec and _spec.loader
    _spec.loader.exec_module(_mod)
    append_jsonl = _mod.append
except Exception as e:  # pragma: no cover - import error handled at runtime
    raise ImportError(f"Could not import jsonl_sink.py: {e}")


def _log_event_impl(record: Dict[str, Any]) -> None:
    """Append ``record`` to a JSONL workflow log file using a common template."""

    wf = get_workflow_id()
    path = SETTINGS.workflows_dir / f"{wf}.jsonl"

    base: Dict[str, Any] = {
        "event_id": record.get("event_id"),
        "status": record.get("status"),
        "timestamp": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "severity": record.get("severity", "info"),
        "workflow_id": get_workflow_id(),
        "details": {},
    }

    for k, v in record.items():
        if k not in {
            "event_id",
            "status",
            "timestamp",
            "severity",
            "workflow_id",
            "details",
        }:
            base.setdefault("details", {})[k] = v
        elif k == "details" and isinstance(v, dict):
            base["details"].update(v)

    SETTINGS.workflows_dir.mkdir(parents=True, exist_ok=True)
    append_jsonl(path, base)


def log_event(record: Dict[str, Any]) -> None:
    """Dispatch to an overridden ``orchestrator.log_event`` if present."""

    orchestrator = sys.modules.get("core.orchestrator")
    override = getattr(orchestrator, "log_event", None) if orchestrator else None
    if override is not None and override is not log_event:
        override(record)
        return
    _log_event_impl(record)
