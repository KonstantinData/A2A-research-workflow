from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator


def test_idle_artifacts_created(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    # Leere Trigger erzwingen
    res = orchestrator.run(triggers=[])
    out = Path(tmp_path / "out" / "exports")
    assert (out / "report.pdf").exists() and (out / "report.pdf").stat().st_size > 1000
    assert (out / "data.csv").exists() and (out / "data.csv").read_text().strip() != "csv"
