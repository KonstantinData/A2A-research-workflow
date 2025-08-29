import datetime as dt
from pathlib import Path
import pytest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations import google_calendar
from core import orchestrator


class _StubEvents:
    def __init__(self, items, call_rec):
        self._items = items
        self._call_rec = call_rec

    def list(self, **kwargs):
        self._call_rec.update(kwargs)
        return self

    def execute(self):
        return {"items": list(self._items)}


class _StubService:
    def __init__(self, items, call_rec):
        self.items = items
        self.call_rec = call_rec

    def events(self):
        return _StubEvents(self.items, self.call_rec)


@pytest.fixture
def stub_time(monkeypatch):
    fixed = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(google_calendar, "_utc_now", lambda: fixed)
    return fixed


def _setup_service(monkeypatch, items):
    rec = {}
    svc = _StubService(items, rec)
    monkeypatch.setattr(google_calendar, "_service", lambda: svc)
    return rec


def test_default_window(monkeypatch, stub_time, tmp_path):
    monkeypatch.chdir(tmp_path)
    call_rec = _setup_service(monkeypatch, [])
    google_calendar.fetch_events()
    assert call_rec["timeMin"] == "2023-12-25T00:00:00Z"
    assert call_rec["timeMax"] == "2024-03-01T00:00:00Z"


def test_env_override(monkeypatch, stub_time, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CALENDAR_MINUTES_BACK", "30")
    monkeypatch.setenv("CALENDAR_MINUTES_FWD", "60")
    call_rec = _setup_service(monkeypatch, [])
    google_calendar.fetch_events()
    assert call_rec["timeMin"] == "2023-12-31T23:30:00Z"
    assert call_rec["timeMax"] == "2024-01-01T01:00:00Z"


def test_duplicate_event_not_skipped(monkeypatch, stub_time, tmp_path):
    monkeypatch.chdir(tmp_path)
    event = {"id": "1", "updated": "2021-01-01T00:00:00Z", "summary": "hit"}
    _setup_service(monkeypatch, [event])
    first = google_calendar.fetch_events()
    assert len(first) == 1
    second = google_calendar.fetch_events()
    assert len(second) == 1


def test_event_updated_still_returned(monkeypatch, stub_time, tmp_path):
    monkeypatch.chdir(tmp_path)
    event = {"id": "1", "updated": "2021-01-01T00:00:00Z", "summary": "hit"}
    _setup_service(monkeypatch, [event])
    first = google_calendar.fetch_events()
    assert len(first) == 1
    event["updated"] = "2021-01-02T00:00:00Z"
    second = google_calendar.fetch_events()
    assert len(second) == 1


def test_fetch_events_includes_creator_and_logs(monkeypatch, stub_time, tmp_path):
    monkeypatch.chdir(tmp_path)
    event = {
        "id": "1",
        "summary": "Meet",
        "description": "desc",
        "start": {"dateTime": "2024-01-01T10:00:00+00:00"},
        "end": {"dateTime": "2024-01-01T11:00:00+00:00"},
        "creator": {"email": "alice@example.com"},
    }
    _setup_service(monkeypatch, [event])
    logs = []

    def fake_log_step(category, status, payload, severity="info"):
        logs.append({"category": category, "status": status, "payload": payload})

    monkeypatch.setattr(google_calendar, "log_step", fake_log_step)
    res = google_calendar.fetch_events()
    assert res == [
        {
            "event_id": "1",
            "summary": "Meet",
            "description": "desc",
            "start": "2024-01-01T10:00:00+00:00",
            "end": "2024-01-01T11:00:00+00:00",
            "creatorEmail": "alice@example.com",
            "creator": {"email": "alice@example.com"},
        }
    ]

    fetched_logs = [l for l in logs if l["status"] == "fetched_events"]
    assert fetched_logs and fetched_logs[0]["payload"]["ids"] == ["1"]


def test_orchestrator_no_triggers(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(orchestrator, "gather_triggers", lambda *a, **k: [])
    records = []
    monkeypatch.setattr(orchestrator, "log_event", lambda r: records.append(r))
    with pytest.raises(SystemExit) as exc:
        orchestrator.run()
    assert exc.value.code == 0
    assert records and records[0]["status"] == "no_triggers"
    assert (
        records[0]["message"]
        == "No calendar or contact events matched trigger words"
    )


def test_extract_company_regex_success(monkeypatch):
    def fake_regex(title, trigger):
        return "Dr. Willmar Schwabe"

    monkeypatch.setattr(google_calendar, "extract_company", fake_regex)

    result = google_calendar.extract_company_ai(
        "Meeting-Vorbereitung Firma Dr. Willmar Schwabe",
        "meeting-vorbereitung",
    )
    assert result == "Dr. Willmar Schwabe"


def test_extract_company_gpt_fallback(monkeypatch):
    def fake_regex(title, trigger):
        return "Unknown"

    monkeypatch.setattr(google_calendar, "extract_company", fake_regex)

    def fake_openai_call(*args, **kwargs):
        return {"choices": [{"message": {"content": "Dr. Willmar Schwabe"}}]}

    monkeypatch.setattr(
        google_calendar.openai.ChatCompletion, "create", fake_openai_call
    )

    result = google_calendar.extract_company_ai(
        "Meeting-Vorbereitung Firma Dr. Willmar Schwabe",
        "meeting-vorbereitung",
    )
    assert result == "Dr. Willmar Schwabe"
