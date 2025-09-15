from pathlib import Path
import csv

from config.settings import SETTINGS

DEFAULT_FIELDS = ["company_name","domain","industry","contact_name","contact_email","source","confidence","notes"]


def export_csv(rows: list, out_path: Path | None = None) -> Path:
    if out_path is None:
        out_path = SETTINGS.exports_dir / "data.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=DEFAULT_FIELDS)
        w.writeheader()
        for r in rows or []:
            w.writerow({k: r.get(k, "") for k in DEFAULT_FIELDS})
    return out_path
