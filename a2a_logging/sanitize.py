"""Utilities for scrubbing personally identifiable information from logs."""

from __future__ import annotations

import hashlib
import re
from typing import Callable, Pattern


_HASH_LENGTH = 12


def _hash_value(value: str) -> str:
    """Return a short hexadecimal hash for ``value`` suitable for log output."""

    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest[:_HASH_LENGTH]


def _replacement(label: str) -> Callable[[re.Match[str]], str]:
    """Return a substitution callback that replaces matches with hashed stand-ins."""

    def _sub(match: re.Match[str]) -> str:
        value = match.group(0)
        return f"<{label}:{_hash_value(value)}>"

    return _sub


_EMAIL_PATTERN: Pattern[str] = re.compile(
    r"(?P<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
)

# Basic international phone number pattern allowing separators and country codes.
_PHONE_PATTERN: Pattern[str] = re.compile(
    r"(?P<phone>\+?\d[\d\s().-]{7,}\d)"
)


def sanitize_message(message: str) -> str:
    """Replace common PII patterns in ``message`` with hashed surrogates."""

    sanitized = _EMAIL_PATTERN.sub(_replacement("email"), message)
    sanitized = _PHONE_PATTERN.sub(_replacement("phone"), sanitized)
    return sanitized


__all__ = ["sanitize_message"]
