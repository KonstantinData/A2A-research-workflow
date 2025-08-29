import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core import orchestrator
from core.utils import log_step


# 1. Ensure demo events are always guarded

def test_demo_events_guarded():
    repo = pathlib.Path(__file__).resolve().parents[1]
    for path in repo.rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text()
        if '"e1"' in text and "DEMO_MODE" not in text and "A2A_DEMO" not in text:
            raise AssertionError(f"unguarded demo event in {path}")


# 2. Ensure orchestrator logs fetch events

def test_orchestrator_logs_fetch():
    orch_path = pathlib.Path(__file__).resolve().parents[1] / "core" / "orchestrator.py"
    text = orch_path.read_text()
    assert "fetch_call" in text and "fetch_return" in text


# 3. Ensure calendar integration logs fetched_events

def test_calendar_logs_events():
    gc_path = pathlib.Path(__file__).resolve().parents[1] / "integrations" / "google_calendar.py"
    text = gc_path.read_text()
    assert "fetched_events" in text


# 4. Runtime self-test: orchestrator must log calendar fetch

def test_runtime_logging(tmp_path):
    os.environ.pop("DEMO_MODE", None)
    os.environ.pop("A2A_DEMO", None)

    log_file = pathlib.Path(__file__).resolve().parents[1] / "logs" / "workflows" / "calendar.jsonl"
    if log_file.exists():
        log_file.unlink()

    def fake_fetch() -> list:
        log_step(
            "calendar",
            "fetched_events",
            {
                "count": 0,
                "time_min": "t0",
                "time_max": "t1",
                "ids": [],
                "summaries": [],
                "creator_emails": [],
            },
        )
        return []

    orchestrator.fetch_events = fake_fetch  # type: ignore
    orchestrator.fetch_contacts = lambda: []  # type: ignore
    orchestrator.reminder_service.check_and_notify = lambda _t: None  # type: ignore
    orchestrator.email_listener.has_pending_events = lambda: False  # type: ignore

    try:
        orchestrator.run()
    except SystemExit:
        pass

    text = log_file.read_text()
    assert "fetch_call" in text
    assert "fetch_return" in text
    assert "fetched_events" in text
    assert "e1" not in text
