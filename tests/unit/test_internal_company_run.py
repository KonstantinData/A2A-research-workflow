from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.internal_company import run as run_module


def test_run_creates_task_for_missing_creator_and_recipient(monkeypatch):
    trigger = {"payload": {"company": "Acme"}}

    captured = {}

    def fake_create_task(trigger_name, missing_fields, employee_email):
        captured["missing_fields"] = missing_fields
        captured["employee_email"] = employee_email
        return {"id": "task-1"}

    class StubSource:
        def run(self, trigger):
            return {"payload": {"summary": "Acme overview"}}

    monkeypatch.setattr(run_module, "INTERNAL_SOURCES", [StubSource()])
    monkeypatch.setattr(run_module, "create_task", fake_create_task)

    result = run_module.run(trigger)

    assert result["payload"]["summary"] == "awaiting employee response"
    assert result["payload"]["task_id"] == "task-1"
    assert captured["missing_fields"] == ["creator", "recipient"]
    assert captured["employee_email"] == ""


def test_run_creates_task_when_summary_missing(monkeypatch):
    trigger = {"creator": "alice", "recipient": "bob"}

    class EmptySource:
        def run(self, trigger):
            return {"payload": {"foo": "bar"}}

    called = {}

    def fake_create_task(trigger_name, missing_fields, employee_email):
        called["missing_fields"] = missing_fields
        called["employee_email"] = employee_email
        return {"id": "task-2"}

    monkeypatch.setattr(run_module, "INTERNAL_SOURCES", [EmptySource()])
    monkeypatch.setattr(run_module, "create_task", fake_create_task)

    result = run_module.run(trigger)

    assert result["payload"]["summary"] == "awaiting employee response"
    assert result["payload"]["task_id"] == "task-2"
    assert called["missing_fields"] == ["summary"]
