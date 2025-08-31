import os
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from output import csv_export, pdf_render


def test_csv_and_meta_on_empty(tmp_path):
    rows = []
    fields = ["company_name", "domain", "email", "phone"]
    os.chdir(tmp_path)
    csv_export.export_csv(rows, fields, reason="no_triggers")

    assert (tmp_path / "output/exports/data.csv").exists()
    meta = json.load(open(tmp_path / "output/exports/meta.json"))
    assert meta["reason"] == "no_triggers"


def test_pdf_placeholder_on_empty(tmp_path):
    rows = []
    os.chdir(tmp_path)
    pdf_render.render_pdf(rows, ["company_name"], {"reason": "no_triggers"})
    assert (tmp_path / "output/exports/report.pdf").exists()

