from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

try:  # pragma: no cover - guard legacy orchestrator
    from core import orchestrator
except ImportError:  # pragma: no cover - orchestrator removed
    pytestmark = pytest.mark.skip(
        reason="Legacy orchestrator removed; calendar idle workflow migrated"
    )
else:
    from integrations import google_calendar
    from config.settings import SETTINGS


def test_missing_creds_yields_idle_artifacts(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setattr(SETTINGS, "output_dir", tmp_path / "out")
    monkeypatch.setattr(SETTINGS, "exports_dir", tmp_path / "out" / "exports")
    monkeypatch.setenv("A2A_TEST_MODE", "1")
    monkeypatch.setattr(google_calendar, "build_user_credentials", lambda scopes: None)
    res = orchestrator.run()
    assert res == {"status": "idle"}
    pdf = SETTINGS.exports_dir / "report.pdf"
    csv = SETTINGS.exports_dir / "data.csv"
    assert pdf.exists() and pdf.stat().st_size > 1000
    assert csv.exists() and csv.stat().st_size > 5
