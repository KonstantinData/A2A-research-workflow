"""CSV export helpers."""

from __future__ import annotations

from pathlib import Path
import csv
import json


def export_csv(data: dict, output_path: Path) -> None:
    """Export ``data`` into ``output_path`` and an accompanying ``details.csv``.

    ``output_path`` defines the main CSV file where top-level keys and values are
    stored. A sibling ``details.csv`` file captures metadata from the ``meta``
    section if present.
    """

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Main CSV with field/value pairs.
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["field", "value"])
        for key, value in data.items():
            if key == "meta":
                continue
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value)
            else:
                value_str = str(value)
            writer.writerow([key, value_str])

    # Details CSV capturing metadata information.
    details_path = path.with_name("details.csv")
    meta = data.get("meta", {})
    with details_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["field", "source", "last_verified_at"])
        for key, info in meta.items():
            if isinstance(info, dict):
                writer.writerow([key, info.get("source", ""), info.get("last_verified_at", "")])
            else:
                writer.writerow([key, str(info), ""])
