"""Miscellaneous helper utilities used across the project.

This module intentionally keeps dependencies light so it can be imported in the
test-suite without requiring any external packages.  Some imports were omitted
in the kata version of the repository which caused ``NameError`` exceptions when
the helpers were exercised.  The tests expect ``normalize_text`` to correctly
handle Unicode dashes and German umlauts and the required/optional field helpers
to function.  We therefore ensure all standard library imports are present.
"""

from __future__ import annotations

import json
import unicodedata
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from logging import getLogger
from pathlib import Path
from typing import Any, Dict, List
import importlib.util as _ilu
import glob
import shutil

_JSONL_PATH = Path(__file__).resolve().parents[1] / "logging" / "jsonl_sink.py"
_spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
append_jsonl = _mod.append

WORKFLOW_ID: str | None = None
SUMMARY: Dict[str, int] = {}


def get_workflow_id() -> str:
    """Return a unique workflow identifier for the current run."""
    global WORKFLOW_ID, SUMMARY
    if WORKFLOW_ID is None:
        WORKFLOW_ID = f"wf-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        SUMMARY = {
            "events_detected": 0,
            "contacts_detected": 0,
            "reminders_sent": 0,
            "reports_generated": 0,
            "mails_sent": 0,
            "errors": 0,
            "warnings": 0,
        }
    return WORKFLOW_ID


def _update_summary(source: str, stage: str, severity: str) -> None:
    global SUMMARY
    if stage == "trigger_detected":
        if source == "calendar":
            SUMMARY["events_detected"] += 1
        elif source == "contacts":
            SUMMARY["contacts_detected"] += 1
    if stage == "reminder_sent":
        SUMMARY["reminders_sent"] += 1
    if stage == "mail_sent":
        SUMMARY["mails_sent"] += 1
    if source == "orchestrator" and stage == "report_generated":
        SUMMARY["reports_generated"] += 1
    if severity == "critical":
        SUMMARY["errors"] += 1
    elif severity == "warning":
        SUMMARY["warnings"] += 1


def log_step(source: str, stage: str, data: Dict[str, Any], *, severity: str = "info") -> None:
    payload = {
        "workflow_id": get_workflow_id(),
        "trigger_source": source,
        "status": stage,
        "severity": severity,
        **data,
    }
    try:
        append_jsonl(Path("logs") / "workflows" / f"{source}.jsonl", payload)
    except Exception as e:  # pragma: no cover - logging shouldn't break tests
        getLogger(__name__).warning("Logging failed: %s", e)
    else:
        _update_summary(source, stage, severity)


def finalize_summary() -> None:
    """Write a digest summary for the current workflow run."""
    wf_id = get_workflow_id()
    path = Path("logs") / "workflows" / "summary.json"
    payload = {"workflow_id": wf_id, **SUMMARY}

    cal_path = Path("logs") / "workflows" / "calendar.jsonl"
    calendar_logs: List[Dict[str, Any]] = []
    if cal_path.exists():
        try:
            with cal_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if rec.get("workflow_id") == wf_id:
                        calendar_logs.append(rec)
        except Exception:
            calendar_logs = []

    if SUMMARY.get("events_detected") or SUMMARY.get("reports_generated"):
        payload["run_mode"] = "live_run"
    elif any(
        e.get("status") in ("fetch_call", "fetched_events") for e in calendar_logs
    ):
        payload["run_mode"] = "calendar_fetch"
    else:
        payload["run_mode"] = "reminder_only"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    # Surface summary in CI logs
    try:
        print(json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass

def normalize_text(text: str) -> str:
    if not text:
        return ""
    # Unicode normalisieren (Gedankenstrich etc. angleichen)
    text = unicodedata.normalize("NFKC", text)
    # Alles klein
    text = text.lower()
    # Alle Varianten von Bindestrichen vereinheitlichen
    dash_variants = ["–", "—", "‐", "‑", "-", "‒", "―"]  # includes U+2011 (non-breaking hyphen)
    for d in dash_variants:
        text = text.replace(d, "-")
    # Umlaute vereinheitlichen (optional für bessere Treffer)
    text = (
        text.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
    )
    return text


@lru_cache()
def _required_fields() -> Dict[str, List[str]]:
    path = Path(__file__).resolve().parents[1] / "config" / "required_fields.json"
    try:
        # ``required_fields.json`` in this kata contains ``//`` style comments
        # which are not part of the JSON specification.  Python's ``json`` module
        # does not ignore these comments which previously caused
        # ``JSONDecodeError`` failures when the file was read.  To keep the
        # configuration human friendly we strip comments before parsing the
        # content.  This is a small helper and avoids pulling in extra
        # dependencies just for lenient JSON parsing.
        text = path.read_text(encoding="utf-8")
        lines = [line.split("//", 1)[0] for line in text.splitlines()]  # remove trailing ``//`` comments
        cleaned = "\n".join(lines)
        return json.loads(cleaned)
    except FileNotFoundError:
        return {}


def required_fields(context: str) -> List[str]:
    return _required_fields().get(context, [])


def optional_fields() -> List[str]:
    """Return optional fields applicable to all contexts."""
    return _required_fields().get("optional", [])


def already_processed(item_id: str, updated: str, logfile) -> bool:
    """Check whether ``item_id`` with ``updated`` is recorded in ``logfile``."""
    path = Path(logfile)
    if not path.exists():
        return False
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("id") == item_id and rec.get("updated") == updated:
                    return True
    except Exception:
        return False
    return False


def mark_processed(item_id: str, updated: str, logfile) -> None:
    """Record ``item_id`` with ``updated`` in ``logfile``."""
    append_jsonl(Path(logfile), {"id": item_id, "updated": updated})


def bundle_logs_into_exports() -> None:
    """Copy workflow logs into the ``output/exports`` directory.

    The orchestrator bundles the logs alongside the generated reports so that
    debugging information is always available with the exported artefacts.  Any
    missing source directory is ignored to keep the helper safe in test
    environments.
    """

    src = Path("logs/workflows")
    dst = Path("output/exports/run_logs")
    dst.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        return
    for p in glob.glob(str(src / "*")):
        try:
            shutil.copy2(p, dst / Path(p).name)
        except Exception:
            continue
