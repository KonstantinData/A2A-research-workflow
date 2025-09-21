"""Helpers for generating unique identifiers used across the app."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import uuid
from typing import Final


_DEFAULT_PREFIX: Final[str] = "EVT"


def _short_uuid() -> str:
    """Return a compact, URL-safe identifier derived from :class:`uuid.UUID`."""

    encoded = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode("ascii").rstrip("=")
    return encoded[:10]


def new_event_id(prefix: str = _DEFAULT_PREFIX) -> str:
    """Generate a unique identifier for events.

    The identifier is composed of ``prefix`` (default ``"EVT"``), the current
    UTC timestamp at second resolution, and a short random component.  The
    resulting identifiers are deterministic in format and easy to scan when
    included in logs or e-mails.
    """

    safe_prefix = (prefix or _DEFAULT_PREFIX).strip().upper() or _DEFAULT_PREFIX
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{safe_prefix}-{timestamp}-{_short_uuid()}"


__all__ = ["new_event_id"]
