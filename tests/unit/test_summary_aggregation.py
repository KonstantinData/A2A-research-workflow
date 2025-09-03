from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.utils import _aggregate_severities

def test_aggregate_counts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = Path("logs/workflows"); p.mkdir(parents=True)
    wf = p / "wf-xyz.jsonl"
    wf.write_text("\n".join([
        json.dumps({"severity": "info"}),
        json.dumps({"severity": "warning"}),
        json.dumps({"severity": "error"}),
        json.dumps({"severity": "warning"}),
    ]), encoding="utf-8")
    sev = _aggregate_severities("wf-xyz")
    assert sev == {"errors": 1, "warnings": 2}
