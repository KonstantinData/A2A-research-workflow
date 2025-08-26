from pathlib import Path
import json

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "jsonl_sink", Path(__file__).resolve().parents[2] / "logging" / "jsonl_sink.py"
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
append = _mod.append


def test_append(tmp_path: Path) -> None:
    file = tmp_path / "log.jsonl"
    append(file, {"a": 1})
    append(file, {"b": 2})
    lines = file.read_text().splitlines()
    assert json.loads(lines[0])["a"] == 1
    assert json.loads(lines[1])["b"] == 2
