from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator
from config.settings import SETTINGS


def test_exports_are_real(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path/"out"))
    monkeypatch.setattr(SETTINGS, "output_dir", tmp_path / "out")
    monkeypatch.setattr(SETTINGS, "exports_dir", tmp_path / "out" / "exports")
    monkeypatch.setenv("A2A_TEST_MODE", "0")
    res = orchestrator.run(triggers=[])
    pdf = SETTINGS.exports_dir / "report.pdf"
    csv = SETTINGS.exports_dir / "data.csv"
    assert pdf.exists() and pdf.stat().st_size > 1000
    assert csv.exists() and csv.stat().st_size > 5
