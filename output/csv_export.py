from pathlib import Path
import csv

DEFAULT_FIELDS = ["company_name","domain","industry","contact_name","contact_email","source","confidence","notes"]


def export_csv(rows: list, out_path: Path = Path("output/exports/data.csv")) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=DEFAULT_FIELDS)
        w.writeheader()
        for r in rows or []:
            w.writerow({k: r.get(k, "") for k in DEFAULT_FIELDS})
    return out_path
