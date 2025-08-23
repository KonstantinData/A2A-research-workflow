from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.internal_company import run as run_module


def test_run_requires_creator_and_recipient():
    trigger = {}
    with pytest.raises(ValueError):
        run_module.run(trigger)


def test_run_requires_summary_in_payload(monkeypatch):
    trigger = {"creator": "alice", "recipient": "bob"}

    class EmptySource:
        def run(self, trigger):
            return {"payload": {}}

    monkeypatch.setattr(run_module, "INTERNAL_SOURCES", [EmptySource()])
    with pytest.raises(ValueError):
        run_module.run(trigger)
