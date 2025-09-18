"""Classification utilities."""

from __future__ import annotations

from typing import Any, Dict, List

# Keyword mapping to DACH economic classifications.  The mapping uses NACE Rev.
# 2 codes as canonical identifiers and stores the equivalent national variants
# (WZ2008 for Germany, ÖNACE 2008 for Austria and NOGA 2008 for Switzerland).
#
# Only a *very* small subset is provided here to keep the example concise.  In a
# real application this data would be loaded from the official open data tables
# of the respective statistical offices.
CLASSIFICATION_KEYWORDS: Dict[str, Dict[str, str]] = {
    "agriculture": {
        "nace": "01",
        "wz2008": "01",
        "onace": "01",
        "noga": "01",
        "label_de": "Landwirtschaft, Jagd und damit verbundene Tätigkeiten",
    },
    "manufacturing": {
        "nace": "28",
        "wz2008": "28",
        "onace": "28",
        "noga": "28",
        "label_de": "Herstellung von Maschinen und Ausrüstungen",
    },
    "software": {
        "nace": "62.01",
        "wz2008": "62.01",
        "onace": "62.01",
        "noga": "62.01",
        "label_de": (
            "Erbringung von Beratungsleistungen auf dem Gebiet der"
            " Informationstechnologie"
        ),
    },
    "consulting": {
        "nace": "70.22",
        "wz2008": "70.22",
        "onace": "70.22",
        "noga": "70.22",
        "label_de": "Unternehmensberatung",
    },
    "retail": {
        "nace": "47.19",
        "wz2008": "47.19",
        "onace": "47.19",
        "noga": "47.19",
        "label_de": "Sonstiger Einzelhandel in Verkaufsräumen",
    },
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


def classify(data: Dict[str, Any]) -> Dict[str, Any]:
    """Classify company data into NACE/WZ2008/ÖNACE/NOGA codes and GPT tags.

    Parameters
    ----------
    data:
        Arbitrary nested structure describing a company. Textual values are
        scanned for keywords which are mapped to classification codes. GPT tags
        may be supplied explicitly via a ``gpt_tags`` key.

    Returns
    -------
    dict
        Dictionary with classification codes for all four systems and collected
        ``gpt_tags``. ``labels`` contains the German description for each
        matched code.
    """

    text = _collect_text(data)

    # Use sets for O(1) duplicate detection
    codes_sets = {
        "nace": set(),
        "wz2008": set(),
        "onace": set(),
        "noga": set(),
    }
    gpt_tags_set = set()
    labels = {"nace": {}, "wz2008": {}, "onace": {}, "noga": {}}

    for keyword, mapping in CLASSIFICATION_KEYWORDS.items():
        if keyword in text:
            for scheme in ("nace", "wz2008", "onace", "noga"):
                code = mapping[scheme]
                if code not in codes_sets[scheme]:
                    codes_sets[scheme].add(code)
                    labels[scheme][code] = mapping["label_de"]
            gpt_tags_set.add(keyword)

    # Add explicit GPT tags
    gpt_tags_set.update(data.get("gpt_tags", []))

    # Convert sets back to lists for output
    result: Dict[str, Any] = {
        "nace": sorted(codes_sets["nace"]),
        "wz2008": sorted(codes_sets["wz2008"]),
        "onace": sorted(codes_sets["onace"]),
        "noga": sorted(codes_sets["noga"]),
        "labels": labels,
        "gpt_tags": sorted(gpt_tags_set),
    }

    return result
