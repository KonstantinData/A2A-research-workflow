"""Feature flag handling loaded from environment variables."""

from __future__ import annotations

import os


def _env_flag(name: str, default: bool) -> bool:
    """Return the boolean value of environment variable ``name``.

    ``default`` is used if the variable is unset. Values ``1``, ``true``,
    ``yes`` and ``on`` (case-insensitive) evaluate to ``True``.
    """
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


# Feature flags with their defaults
USE_PUSH_TRIGGERS = _env_flag("USE_PUSH_TRIGGERS", False)
ENABLE_PRO_SOURCES = _env_flag("ENABLE_PRO_SOURCES", False)
ATTACH_PDF_TO_HUBSPOT = _env_flag("ATTACH_PDF_TO_HUBSPOT", True)


__all__ = [
    "USE_PUSH_TRIGGERS",
    "ENABLE_PRO_SOURCES",
    "ATTACH_PDF_TO_HUBSPOT",
]
