"""Simple classification helpers.

This module provides a tiny keyword based classifier used during tests.  It is
not meant to be exhaustive but gives the orchestrator something deterministic
to work with.  The classifier inspects a free form ``description`` field and
assigns a WZ2008 code and a set of GPT style tags based on keyword matches.

The mapping is intentionally minimal – it only covers a couple of common
keywords so that unit tests can exercise the consolidation pipeline without
requiring external services.
"""

from __future__ import annotations

from typing import Any, Dict, List


# Very small mapping of keywords to WZ2008 industry codes.  The keywords are
# matched case‑insensitively against the provided description text.
_WZ_KEYWORDS = {
    "software": "6201",  # Software development
    "consulting": "7022",  # Business consulting
}


def classify(data: Dict[str, Any]) -> Dict[str, List[str]]:
    """Classify company information into WZ2008 codes and GPT tags.

    Parameters
    ----------
    data:
        A dictionary that may contain a ``description`` field with arbitrary
        text.  The text is inspected for known keywords.

    Returns
    -------
    dict
        ``{"wz2008": [...], "gpt_tags": [...]}`` – both lists may be empty
        when no keywords were detected.
    """

    description = (data.get("description") or "").lower()

    wz_codes: List[str] = []
    tags: List[str] = []
    for keyword, code in _WZ_KEYWORDS.items():
        if keyword in description:
            wz_codes.append(code)
            tags.append(keyword)

    return {"wz2008": wz_codes, "gpt_tags": tags}


__all__ = ["classify"]

