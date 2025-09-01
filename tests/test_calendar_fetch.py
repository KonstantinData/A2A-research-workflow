import datetime as dt
from pathlib import Path
import pytest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations import google_calendar


class _StubEvents:
    def __init__(self, pages, rec):
        self.pages = pages
        self.rec = rec
        self.kw = None

    def list(self, **kwargs):
        self.kw = kwargs
        self.rec.append(kwargs)
        return self

    def execute(self):
        key = (self.kw["calendarId"], self.kw.get("pageToken"))
        return self.pages.get(key, {"items": []})


class _StubService:
    def __init__(self, pages, rec):
        self.pages = pages
        self.rec = rec

    def events(self):
        return _StubEvents(self.pages, self.rec)

    class _CalList:
        def get(self, calendarId=None):
            return self

        def execute(self):
            return {}

    def calendarList(self):
        return self._CalList()


@pytest.fixture
def stub_time(monkeypatch):
    fixed = dt.datetime(2024, 1, 1)

    class _FixedDateTime(dt.datetime):
        @classmethod
        def utcnow(cls):
            return fixed

    monkeypatch.setattr(google_calendar.dt, "datetime", _FixedDateTime)
    return fixed


def _setup_service(monkeypatch, pages):
    rec = []
    svc = _StubService(pages, rec)
    monkeypatch.setattr(google_calendar, "build", lambda *a, **k: svc)
    monkeypatch.setattr(google_calendar, "build_user_credentials", lambda scopes: object())
    return rec


def test_time_window_defaults(monkeypatch, stub_time, tmp_path):
    monkeypatch.chdir(tmp_path)
    rec = _setup_service(monkeypatch, {("primary", None): {"items": []}})
    google_calendar.fetch_events()
    args = rec[0]
    assert args["timeMin"] == "2023-12-31T00:00:00+00:00"
    assert args["timeMax"] == "2024-01-15T00:00:00+00:00"


def test_env_override(monkeypatch, stub_time, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CAL_LOOKBACK_DAYS", "2")
    monkeypatch.setenv("CAL_LOOKAHEAD_DAYS", "3")
    monkeypatch.setattr(google_calendar, "LOOKBACK_DAYS", 2)
    monkeypatch.setattr(google_calendar, "LOOKAHEAD_DAYS", 3)
    rec = _setup_service(monkeypatch, {("primary", None): {"items": []}})
    google_calendar.fetch_events()
    args = rec[0]
    assert args["timeMin"] == "2023-12-30T00:00:00+00:00"
    assert args["timeMax"] == "2024-01-04T00:00:00+00:00"


def test_multi_calendar_and_pagination(monkeypatch, stub_time, tmp_path):
    monkeypatch.chdir(tmp_path)
    pages = {
        ("cal1", None): {"items": [{"id": "1"}], "nextPageToken": "t"},
        ("cal1", "t"): {"items": [{"id": "2"}]},
        ("cal2", None): {"items": [{"id": "3"}]},
    }
    monkeypatch.setenv("GOOGLE_CALENDAR_IDS", "cal1,cal2")
    monkeypatch.setattr(google_calendar, "CAL_IDS", ["cal1", "cal2"])
    rec = _setup_service(monkeypatch, pages)
    logs = []

    def fake_log_step(category, status, payload, severity="info"):
        logs.append({"category": category, "status": status, "payload": payload})

    monkeypatch.setattr(google_calendar, "log_step", fake_log_step)
    res = google_calendar.fetch_events()
    assert [e["event_id"] for e in res] == ["1", "2", "3"]
    fetch_logs = [l for l in logs if l["status"] == "fetch_ok"]
    assert fetch_logs and fetch_logs[0]["payload"]["calendars"] == ["cal1", "cal2"]

