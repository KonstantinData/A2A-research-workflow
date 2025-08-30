import pathlib
import re


DEMO_EVENT = "e" + "1"


def self_test() -> None:
    repo = pathlib.Path(__file__).resolve().parent

    pattern = re.compile(r'event_id\s*[:=]\s*["\']' + DEMO_EVENT + r'["\']')
    for path in repo.glob("**/*.py"):
        if "tests" in path.parts or path.name == "self_test.py":
            continue
        text = path.read_text()
        if pattern.search(text):
            if "DEMO_MODE" not in text and "A2A_DEMO" not in text:
                raise AssertionError(f"{path} contains demo event without guard")

    orch_path = repo / "core" / "orchestrator.py"
    orch_text = orch_path.read_text()
    if len(re.findall(r"fetch_events\(", orch_text)) != 1:
        raise AssertionError("fetch_events not called exactly once in orchestrator")
    if 'log_step("calendar", "fetch_return"' not in orch_text:
        raise AssertionError("missing fetch_return log step")

    gc_path = repo / "integrations" / "google_calendar.py"
    gc_text = gc_path.read_text()
    for token in ["fetch_call", "raw_api_response", "fetched_events"]:
        if token not in gc_text:
            raise AssertionError(f"missing {token} logging")
    if "time_min" not in gc_text or "time_max" not in gc_text or "ids" not in gc_text:
        raise AssertionError("fetched_events logging missing fields")
    if f'"{DEMO_EVENT}"' in gc_text:
        raise AssertionError("demo event must be removed from calendar integration")

