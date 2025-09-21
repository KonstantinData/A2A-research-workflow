"""Shared retry/backoff policy for network operations."""
from __future__ import annotations

import random
from typing import Final

MAX_ATTEMPTS: Final[int] = 4
BASE_DELAY_S: Final[float] = 1.5
JITTER_S: Final[float] = 0.75
_MAX_DELAY_S: Final[float] = 60.0


def _compute_delay(retries: int) -> float:
    """Return the exponential backoff delay for ``retries`` attempts."""

    attempt = max(1, int(retries))
    delay = BASE_DELAY_S * (2 ** (attempt - 1))
    jitter = random.uniform(0.0, JITTER_S) if JITTER_S > 0 else 0.0
    return min(delay + jitter, _MAX_DELAY_S)


async def backoff(retries: int) -> float:
    """Asynchronously compute the delay for the given retry attempt."""

    return _compute_delay(retries)


async def default_backoff(retries: int) -> float:
    """Backward-compatible alias for the default async backoff policy."""

    return await backoff(retries)


def backoff_seconds(retries: int) -> float:
    """Synchronous helper returning the delay for ``retries`` attempts."""

    return _compute_delay(retries)


__all__ = [
    "MAX_ATTEMPTS",
    "BASE_DELAY_S",
    "JITTER_S",
    "backoff",
    "default_backoff",
    "backoff_seconds",
]
