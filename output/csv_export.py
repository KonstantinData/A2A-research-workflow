# output/csv_export.py
"""CSV export for consolidated data."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import csv
import json


def export_csv(data: Dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # write flattened key/value pairs
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["field", "value"])
        for k, v in data.items():
            if k == "meta":
                continue
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            w.writerow([k, str(v)])
