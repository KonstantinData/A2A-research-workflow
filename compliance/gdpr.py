"""GDPR compliance utilities.

This module provides helpers for removing or redacting non-public personal
information ("PII") from arbitrary Python data structures. The primary entry
point is :func:`anonymize` which recursively traverses the provided object and
removes common PII fields such as names, e‑mail addresses or phone numbers.

The implementation is intentionally lightweight – it does not aim to cover
every possible type of PII, but instead provides sensible defaults that are
sufficient for unit tests and simple data structures.
"""

from __future__ import annotations

from typing import Any
import re

# Common keys that typically contain personal information. Keys are matched in
# a case-insensitive manner.
SENSITIVE_KEYS = {
    "name",
    "email",
    "phone",
    "address",
    "ssn",
}

# Regular expressions used to find e‑mail addresses and phone numbers inside
# free-form text values.
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\-\s()]{7,}\d")


def _redact_string(value: str) -> str:
    """Redact obvious personal information from a string."""

    value = EMAIL_RE.sub("<redacted>", value)
    value = PHONE_RE.sub("<redacted>", value)
    return value


def anonymize(data: Any) -> Any:
    """Remove non-public personal data from ``data``.

    The function accepts any Python object and returns a new object with common
    personal information removed or redacted. Dictionaries and lists are
    traversed recursively. Strings are scanned for e‑mail addresses and phone
    numbers which are replaced with ``"<redacted>"``.
    """

    if isinstance(data, dict):
        sanitized: dict[str, Any] = {}
        for key, value in data.items():
            if key.lower() in SENSITIVE_KEYS:
                continue
            sanitized[key] = anonymize(value)
        return sanitized

    if isinstance(data, list):
        return [anonymize(item) for item in data]

    if isinstance(data, str):
        return _redact_string(data)

    return data


__all__ = ["anonymize"]
