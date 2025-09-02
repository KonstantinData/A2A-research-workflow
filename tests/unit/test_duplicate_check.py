"""Tests for duplicate detection."""

from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.duplicate_check import is_duplicate
from core.orchestrator import is_event_active


def test_is_duplicate_detects_similarity():
    record = {"name": "Acme GmbH"}
    existing = [{"name": "ACME gmbh"}]
    assert is_duplicate(record, existing) is True


def test_is_duplicate_rejects_different_names():
    record = {"name": "Acme"}
    existing = [{"name": "Different"}]
    assert is_duplicate(record, existing) is False


def test_is_event_active_pending_vs_resumed(tmp_path, monkeypatch):
    logs_dir = tmp_path / "logs" / "workflows"
    logs_dir.mkdir(parents=True)
    log_file = logs_dir / "wf-test.jsonl"

    # Initial pending status means the event is considered active
    log_file.write_text(json.dumps({"event_id": "1", "status": "pending"}) + "\n")
    monkeypatch.chdir(tmp_path)
    assert is_event_active("1") is True

    # A subsequent resumed status should allow processing again
    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event_id": "1", "status": "resumed"}) + "\n")
    assert is_event_active("1") is False
