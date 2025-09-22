from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:  # pragma: no cover - guard legacy orchestrator
    from core import orchestrator
except ImportError:  # pragma: no cover - orchestrator removed
    pytestmark = pytest.mark.skip(
        reason="Legacy orchestrator removed; idle artifact workflow migrated"
    )
else:
    from config.settings import SETTINGS


def test_idle_artifacts_created(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setattr(SETTINGS, "output_dir", tmp_path / "out")
    monkeypatch.setattr(SETTINGS, "exports_dir", tmp_path / "out" / "exports")
    # Leere Trigger erzwingen
    res = orchestrator.run(triggers=[])
    out = SETTINGS.exports_dir
    assert (out / "report.pdf").exists() and (out / "report.pdf").stat().st_size > 1000
    assert (out / "data.csv").exists() and (out / "data.csv").read_text().strip() != "csv"
