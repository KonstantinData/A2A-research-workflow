from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator


def test_exports_are_real(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path/"out"))
    monkeypatch.setenv("A2A_TEST_MODE", "0")
    res = orchestrator.run(triggers=[])
    pdf = Path(tmp_path/"out"/"exports"/"report.pdf")
    csv = Path(tmp_path/"out"/"exports"/"data.csv")
    assert pdf.exists() and pdf.stat().st_size > 1000
    assert csv.exists() and csv.stat().st_size > 5
