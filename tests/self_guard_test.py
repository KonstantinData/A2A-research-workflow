import json
import os
from pathlib import Path


def test_calendar_fetch_logging_and_demo_mode():
    path = Path(__file__).resolve().parents[1] / "logs" / "workflows" / "calendar.jsonl"
    events = []
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except Exception:
                        continue

    statuses = [e.get("status") for e in events]
    assert "fetch_call" in statuses
    assert "raw_api_response" in statuses
    assert "fetched_events" in statuses

    demo_flags = {os.getenv("DEMO_MODE"), os.getenv("A2A_DEMO")}
    ids = [e.get("event_id") for e in events]
    if "e1" in ids:
        assert "1" in demo_flags, "Demo event found without DEMO_MODE/A2A_DEMO"
