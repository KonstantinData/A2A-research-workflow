from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator, validate

_SCHEMAS: dict[str, Dict[str, Any]] = {}
_BASE = Path(__file__).resolve().parents[2] / "schemas" / "events"


def _load(name: str) -> Dict[str, Any]:
    p = _BASE / f"{name}.schema.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def validate_event_payload(event_type: str, payload: Dict[str, Any] | None) -> None:
    schema = _SCHEMAS.get(event_type)
    if schema is None:
        schema = _load(event_type)
        _SCHEMAS[event_type] = schema
    if not schema:
        return  # no schema registered → nothing to validate
    Draft202012Validator.check_schema(schema)
    validate(instance=payload or {}, schema=schema)
