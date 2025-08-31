from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator
from integrations import google_calendar


def test_missing_creds_yields_idle_artifacts(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("A2A_TEST_MODE", "1")
    monkeypatch.setattr(google_calendar, "build_user_credentials", lambda scopes: None)
    res = orchestrator.run()
    assert res == {"status": "idle"}
    pdf = Path(tmp_path / "out" / "exports" / "report.pdf")
    csv = Path(tmp_path / "out" / "exports" / "data.csv")
    assert pdf.exists() and pdf.stat().st_size > 1000
    assert csv.exists() and csv.stat().st_size > 5
