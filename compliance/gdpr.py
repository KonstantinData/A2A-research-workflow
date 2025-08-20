"""GDPR compliance utilities."""

from __future__ import annotations

import re
from typing import Any, Dict


_PII_KEYS = {"name", "email", "phone"}
_EMAIL_RE = re.compile(r"[\w.%-]+@[\w.-]+")


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return _EMAIL_RE.sub("<redacted>", value)
    return value


def anonymize(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove common personal identifiers from ``data``."""

    cleaned: Dict[str, Any] = {}
    for key, value in data.items():
        if key in _PII_KEYS:
            continue
        if isinstance(value, dict):
            cleaned[key] = anonymize(value)
        else:
            cleaned[key] = _redact(value)
    return cleaned


__all__ = ["anonymize"]
