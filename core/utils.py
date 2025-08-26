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
from functools import lru_cache
from pathlib import Path
from typing import Dict, List
import importlib.util as _ilu

_JSONL_PATH = Path(__file__).resolve().parents[1] / "logging" / "jsonl_sink.py"
_spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
append_jsonl = _mod.append

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
