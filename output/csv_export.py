# output/csv_export.py
"""CSV export helpers.

The project historically exposed :func:`export_csv` which accepted a dictionary
and a target :class:`~pathlib.Path` and wrote flattened key/value pairs.  For
the new workflow exports we need a more robust variant that always writes the
expected column headers and records a ``meta.json`` file when no rows are
exported.  To remain backwards compatible the function now accepts both call
styles:

``export_csv(mapping, path)``
    Legacy behaviour – write flattened key/value pairs to ``path``.

``export_csv(rows, fields, reason=None)``
    New behaviour – write rows with ``fields`` headers to
    ``output/exports/data.csv`` and create a ``meta.json`` file when ``rows`` is
    empty.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List
from datetime import datetime
import csv
import json


def _export_kv(data: Dict[str, Any], out_path: Path) -> None:
    """Backward compatible key/value export used in legacy tests."""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["field", "value"])
        for key, value in data.items():
            if key == "meta":
                continue
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            writer.writerow([key, str(value)])


def export_csv(
    data_or_rows: Any,
    out_path_or_fields: Any,
    reason: str | None = None,
) -> None:
    """Export consolidated data to CSV.

    Parameters
    ----------
    data_or_rows:
        Either a mapping of key/value pairs (legacy behaviour) or an iterable of
        row dictionaries.
    out_path_or_fields:
        ``Path`` for the legacy behaviour or an iterable of field names for the
        new style export.
    reason:
        Optional explanation recorded in ``meta.json`` when no rows were
        exported.  Only used in the new behaviour.
    """

    # Legacy behaviour: ``export_csv(mapping, path)``
    if isinstance(out_path_or_fields, (str, Path)):
        _export_kv(data_or_rows, Path(out_path_or_fields))
        return

    # New behaviour: ``export_csv(rows, fields, reason=None)``
    rows = list(data_or_rows or [])
    fields: List[str] = list(out_path_or_fields or [])

    outdir = Path("output/exports")
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / "data.csv"

    with csv_path.open("w", encoding="utf-8") as f:
        f.write(",".join(fields) + "\n")
        for row in rows:
            f.write(",".join(str(row.get(col, "")) for col in fields) + "\n")

    if not rows:
        meta = {
            "exported_rows": 0,
            "reason": reason or "no_valid_triggers_or_missing_required_fields",
            "timestamp": datetime.utcnow().isoformat(),
        }
        with (outdir / "meta.json").open("w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
