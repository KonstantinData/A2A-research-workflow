"""Minimal CSV export functionality."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict


def export_csv(data: Dict[str, Any], output_path: str | Path) -> None:
    """Write ``data`` to ``output_path`` in CSV format.

    The function expects a flat dictionary and writes a single-row CSV file with
    a header.  It is intentionally tiny but sufficient for unit tests.
    """

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(data.keys()))
        writer.writeheader()
        writer.writerow(data)


__all__ = ["export_csv"]

