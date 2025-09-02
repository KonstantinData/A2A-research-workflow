import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from output import csv_export, pdf_render


def test_csv_with_header_on_empty(tmp_path):
    rows = []
    os.chdir(tmp_path)
    csv_export.export_csv(rows)

    csv_path = tmp_path / "output/exports/data.csv"
    assert csv_path.exists()
    contents = csv_path.read_text().splitlines()
    assert contents == [",".join(csv_export.DEFAULT_FIELDS)]


def test_pdf_created_on_empty(tmp_path):
    rows = []
    os.chdir(tmp_path)
    pdf_render.render_pdf(rows, ["company_name"], {"reason": "no_triggers"})
    assert (tmp_path / "output/exports/report.pdf").exists()

