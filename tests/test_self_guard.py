import os
import pathlib
import sys
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core import orchestrator
from core.utils import log_step


# 1. No unguarded demo events

def test_demo_events_guarded():
    repo = pathlib.Path(__file__).resolve().parents[1]
    demo_path = repo / "core" / "demo_mode.py"
    for path in repo.rglob("*.py"):
        if "tests" in path.parts or path == demo_path or path.name == "self_test.py":
            continue
        text = path.read_text()
        assert '"e1"' not in text, f"demo event leakage in {path}"


# 2. Required log statements exist

def test_required_log_statements():
    repo = pathlib.Path(__file__).resolve().parents[1]
    orch_text = (repo / "core" / "orchestrator.py").read_text()
    assert "fetch_return" in orch_text
    gc_text = (repo / "integrations" / "google_calendar.py").read_text()
    for token in ["fetch_call", "raw_api_response", "fetched_events"]:
        assert token in gc_text


# 3. Runtime validation

def test_runtime_logging(monkeypatch):
    os.environ.pop("DEMO_MODE", None)
    os.environ.pop("A2A_DEMO", None)

    log_file = pathlib.Path(__file__).resolve().parents[1] / "logs" / "workflows" / "calendar.jsonl"
    if log_file.exists():
        log_file.unlink()

    sample_event = {"event_id": "live1", "summary": "X", "creatorEmail": "a@b.c"}

    def fake_fetch():
        log_step("calendar", "fetch_call", {})
        log_step("calendar", "raw_api_response", {"response": {}})
        log_step(
            "calendar",
            "fetched_events",
            {
                "count": 1,
                "time_min": "t0",
                "time_max": "t1",
                "ids": [sample_event["event_id"]],
                "summaries": [sample_event["summary"]],
                "creator_emails": [sample_event["creatorEmail"]],
            },
        )
        return [sample_event]

    monkeypatch.setattr(orchestrator, "fetch_events", fake_fetch)
    monkeypatch.setattr(orchestrator, "fetch_contacts", lambda: [])
    monkeypatch.setattr(orchestrator.reminder_service, "check_and_notify", lambda _t: None)
    monkeypatch.setattr(orchestrator.email_listener, "has_pending_events", lambda: False)

    try:
        orchestrator.run()
    except SystemExit:
        pass

    text = log_file.read_text()
    assert "fetch_call" in text
    assert "raw_api_response" in text
    assert "fetch_return" in text
    assert "fetched_events" in text
    assert '"e1"' not in text


def test_runtime_blocks_demo(monkeypatch):
    os.environ.pop("DEMO_MODE", None)
    os.environ.pop("A2A_DEMO", None)

    def fake_fetch():
        log_step("calendar", "fetch_call", {})
        log_step("calendar", "raw_api_response", {"response": {}})
        log_step(
            "calendar",
            "fetched_events",
            {
                "count": 1,
                "time_min": "t0",
                "time_max": "t1",
                "ids": ["e1"],
                "summaries": ["demo"],
                "creator_emails": ["demo@example.com"],
            },
        )
        return [{"event_id": "e1"}]

    monkeypatch.setattr(orchestrator, "fetch_events", fake_fetch)
    monkeypatch.setattr(orchestrator, "fetch_contacts", lambda: [])
    monkeypatch.setattr(orchestrator.reminder_service, "check_and_notify", lambda _t: None)
    monkeypatch.setattr(orchestrator.email_listener, "has_pending_events", lambda: False)

    with pytest.raises(SystemExit):
        orchestrator.run()

