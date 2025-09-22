import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from output import csv_export, pdf_render
from config.settings import SETTINGS


def test_csv_with_header_on_empty(tmp_path):
    rows = []
    os.chdir(tmp_path)
    csv_export.export_csv(rows)

    csv_path = SETTINGS.exports_dir / "data.csv"
    assert csv_path.exists()
    contents = csv_path.read_text().splitlines()
    assert contents == [",".join(csv_export.DEFAULT_FIELDS)]


def test_pdf_created_on_empty(tmp_path, monkeypatch):
    rows = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIVE_MODE", "0")
    pdf_render.render_pdf(rows, ["company_name"], {"reason": "no_triggers"})
    assert (SETTINGS.exports_dir / "report.pdf").exists()


def test_pdf_raises_in_live_mode(tmp_path, monkeypatch):
    rows = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIVE_MODE", "1")
    monkeypatch.setattr(SETTINGS, "live_mode", 1, raising=False)
    monkeypatch.setattr(pdf_render, "HTML", None)
    with pytest.raises(RuntimeError):
        pdf_render.render_pdf(rows, ["company_name"], {"reason": "no_triggers"})


def test_legacy_wrapper_emits_warning(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIVE_MODE", "0")
    payload = {"rows": [], "fields": [], "meta": {"reason": "legacy"}}
    out_path = SETTINGS.exports_dir / "legacy.pdf"
    with pytest.deprecated_call():
        pdf_render.render_pdf_from_mapping(payload, out_path)
    assert out_path.exists()

