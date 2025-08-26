# core/summarize.py
"""Utilities for summarising free-form text.

The project only requires a very small amount of summarisation logic.  The
``summarize_notes`` function included here intentionally keeps dependencies to
an absolute minimum and implements a tiny heuristic summariser.  It extracts
the first sentence of the provided text and falls back to simple truncation
when no obvious sentence boundary is found.

The helper is deliberately lightweight so it can run in restricted execution
environments such as the test suite.
"""

from __future__ import annotations

from typing import Optional


def summarize_notes(text: Optional[str], max_length: int = 200) -> str:
    """Return a short human readable summary of ``text``.

    Parameters
    ----------
    text:
        Raw notes string. ``None`` or empty values result in an empty summary.
    max_length:
        Maximum number of characters for the returned summary.

    The function uses a very small heuristic: it tries to return the first
    sentence (up to ``max_length`` characters).  If no sentence terminator is
    present it falls back to truncating the text.  Newlines are treated as
    spaces.  The goal is not perfect linguistic summarisation but a stable and
    deterministic implementation that is good enough for unit tests.
    """

    if not text:
        return ""

    # Normalise whitespace and strip leading/trailing spaces.
    cleaned = " ".join(str(text).split())

    # Attempt to extract the first sentence.  This keeps the implementation
    # dependency free while still providing useful behaviour.
    for sep in (". ", "! ", "? "):
        if sep in cleaned:
            candidate = cleaned.split(sep, 1)[0]
            if len(candidate) <= max_length:
                return candidate.strip()

    # Fallback: simple truncation with ellipsis when the text is very long.
    if len(cleaned) > max_length:
        return cleaned[: max_length].rstrip() + "..."
    return cleaned


__all__ = ["summarize_notes"]

