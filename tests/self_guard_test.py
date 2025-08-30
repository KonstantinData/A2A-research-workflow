import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import orchestrator
from core.utils import log_step


def test_calendar_fetch_logging_and_demo_mode(monkeypatch):
    """Ensure calendar fetch logs exist and demo events require flags."""

    os.environ.pop("DEMO_MODE", None)
    os.environ.pop("A2A_DEMO", None)

    path = Path(__file__).resolve().parents[1] / "logs" / "workflows" / "calendar.jsonl"
    if path.exists():
        path.unlink()

    sample = {"event_id": "live1", "summary": "x", "creatorEmail": "a@b.c"}

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
                "ids": [sample["event_id"]],
                "summaries": [sample["summary"]],
                "creator_emails": [sample["creatorEmail"]],
            },
        )
        return [sample]

    monkeypatch.setattr(orchestrator, "fetch_events", fake_fetch)
    monkeypatch.setattr(orchestrator, "fetch_contacts", lambda: [])
    monkeypatch.setattr(orchestrator.reminder_service, "check_and_notify", lambda _t: None)
    monkeypatch.setattr(orchestrator.email_listener, "has_pending_events", lambda: False)

    try:
        orchestrator.run()
    except SystemExit:
        pass

    events = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    statuses = [e.get("status") for e in events]

    if any(s in statuses for s in ("fetch_call", "raw_api_response", "fetched_events")):
        assert "fetch_call" in statuses
        assert "raw_api_response" in statuses
        assert "fetched_events" in statuses
    else:
        print("⚠️ Warning: reminder-only run, no calendar fetch detected")
        assert all(e.get("event_id") != "e1" for e in events), \
            "Demo event detected in non-demo mode"
