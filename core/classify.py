"""Classification utilities."""

from __future__ import annotations

from typing import Any, Dict, List

# Simple keyword mapping to WZ2008 classification codes.
# This is a tiny subset for demonstration purposes only.
WZ2008_KEYWORDS: Dict[str, str] = {
    "agriculture": "01",
    "manufacturing": "28",
    "software": "62.01",
    "consulting": "70.22",
    "retail": "47.19",
}


def _collect_text(data: Any) -> str:
    """Recursively collect text from ``data``.

    ``data`` may be nested ``dict``/``list``/``str`` structures. Any text
    encountered is concatenated into a single lowercase string which is then
    analysed for keyword matches.
    """
    parts: List[str] = []
    if isinstance(data, str):
        parts.append(data.lower())
    elif isinstance(data, dict):
        for value in data.values():
            parts.append(_collect_text(value))
    elif isinstance(data, list):
        for value in data:
            parts.append(_collect_text(value))
    return " ".join(p for p in parts if p)


def classify(data: Dict[str, Any]) -> Dict[str, List[str]]:
    """Classify company data into WZ2008 codes and GPT tags.

    Parameters
    ----------
    data:
        Arbitrary nested structure describing a company. Textual values are
        scanned for keywords which are mapped to WZ2008 codes. GPT tags may be
        supplied explicitly via a ``gpt_tags`` key.

    Returns
    -------
    dict
        Dictionary with ``wz2008`` and ``gpt_tags`` keys mapping to lists of
        matched codes/tags.
    """
    text = _collect_text(data)

    wz_codes: List[str] = []
    tags: List[str] = []

    for keyword, code in WZ2008_KEYWORDS.items():
        if keyword in text:
            if code not in wz_codes:
                wz_codes.append(code)
            if keyword not in tags:
                tags.append(keyword)

    for tag in data.get("gpt_tags", []):
        if tag not in tags:
            tags.append(tag)

    return {"wz2008": wz_codes, "gpt_tags": tags}


__all__ = ["classify"]
