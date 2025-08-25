from pathlib import Path

import pytest

from agents import agent_internal_search
from core import orchestrator, utils
from integrations import google_calendar


@pytest.fixture(autouse=True)
def _chdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _stub_pdf(data, path):
    path.write_text("pdf")


def _stub_csv(data, path):
    path.write_text("csv")


def _trigger(payload):
    payload = dict(payload)
    payload.setdefault("id", "1")
    return {
        "source": "calendar",
        "creator": payload.get("email"),
        "recipient": payload.get("email"),
        "payload": payload,
    }


def test_all_fields_present(monkeypatch):
    send_called = {"rem": 0}
    monkeypatch.setattr(agent_internal_search, "internal_run", lambda t: {"payload": {}})
    monkeypatch.setattr(agent_internal_search.email_sender, "send", lambda **k: send_called.__setitem__("rem", send_called["rem"] + 1))
    monkeypatch.setattr(agent_internal_search.email_sender, "send_email", lambda **k: None)
    payload = {"company": "ACME", "domain": "acme.com", "email": "a@b", "phone": "1"}
    res = agent_internal_search.run(_trigger(payload))
    assert res.get("status") != "missing_fields"
    assert send_called["rem"] == 0


def test_missing_field_triggers_reminder(monkeypatch):
    logs = []
    orig_log = orchestrator.log_event

    def capture(rec):
        logs.append(rec)
        orig_log(rec)

    monkeypatch.setattr(orchestrator, "log_event", capture)
    send_calls = []
    monkeypatch.setattr(agent_internal_search, "internal_run", lambda t: {"payload": {}})
    monkeypatch.setattr(agent_internal_search.email_sender, "send", lambda **kw: send_calls.append(kw))
    monkeypatch.setattr(agent_internal_search.email_sender, "send_email", lambda **k: None)
    trig = _trigger({"company": "ACME", "email": "a@b", "phone": "1"})
    with pytest.raises(SystemExit) as exc:
        orchestrator.run(
            triggers=[trig],
            researchers=[agent_internal_search.run],
            pdf_renderer=_stub_pdf,
            csv_exporter=_stub_csv,
            hubspot_upsert=lambda d: None,
            hubspot_attach=lambda p, c: None,
            hubspot_check_existing=lambda cid: None,
        )
    assert exc.value.code == 0
    assert send_calls and send_calls[0]["to"] == "a@b"
    assert any(r.get("status") == "pending" for r in logs)
    files = list(Path("logs/workflows").glob("*.jsonl"))
    content = "".join(f.read_text() for f in files)
    assert '"status": "missing_fields"' in content
    assert '"status": "reminder_sent"' in content


def test_only_optional_missing(monkeypatch):
    logs = []
    monkeypatch.setattr(agent_internal_search, "internal_run", lambda t: {"payload": {}})
    monkeypatch.setattr(agent_internal_search.email_sender, "send", lambda **k: None)
    monkeypatch.setattr(agent_internal_search.email_sender, "send_email", lambda **k: None)

    def capture(rec):
        logs.append(rec)

    monkeypatch.setattr(agent_internal_search, "_log_workflow", capture)
    payload = {"company": "ACME", "domain": "acme.com"}
    res = agent_internal_search.run(_trigger(payload))
    assert res.get("status") != "missing_fields"
    assert any(r.get("status") == "missing_optional_fields" for r in logs)


def test_duplicate_event_skipped(monkeypatch):
    monkeypatch.setattr(google_calendar, "load_trigger_words", lambda: ["Meet"])

    def fake_events():
        return [{"id": "e1", "iCalUID": "e1", "updated": "u1", "summary": "Meet ACME", "description": ""}]

    monkeypatch.setattr(google_calendar, "_calendar_ids", lambda cid: ["primary"])

    class FakeReq:
        def events(self):
            return self

        def list(self, **kw):
            return self

        def execute(self):
            return {"items": fake_events()}

    monkeypatch.setattr(google_calendar, "_service", lambda: FakeReq())
    utils.mark_processed("e1", "u1", Path("logs/processed_events.jsonl"))
    events = google_calendar.fetch_events()
    assert events == []
    content = Path("logs/workflows/calendar.jsonl").read_text()
    assert '"status": "skipped"' in content


def test_email_reply_resumes(monkeypatch):
    called = {"internal": 0}
    monkeypatch.setattr(
        agent_internal_search,
        "internal_run",
        lambda t: (called.__setitem__("internal", called["internal"] + 1) or {"payload": {}}),
    )
    monkeypatch.setattr(agent_internal_search.email_sender, "send", lambda **k: None)
    monkeypatch.setattr(agent_internal_search.email_sender, "send_email", lambda **k: None)
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)
    monkeypatch.setattr(
        orchestrator.email_reader,
        "fetch_replies",
        lambda: [{"creator": "a@b", "task_id": "1", "fields": {"domain": "acme.com"}}],
    )
    trig = _trigger({"company": "ACME", "email": "a@b", "phone": "1"})
    orchestrator.run(
        triggers=[trig],
        researchers=[agent_internal_search.run],
        consolidate_fn=lambda x: {},
        pdf_renderer=_stub_pdf,
        csv_exporter=_stub_csv,
        hubspot_upsert=lambda d: None,
        hubspot_attach=lambda p, c: None,
        hubspot_check_existing=lambda cid: None,
    )
    assert called["internal"] == 1
    content = "".join(f.read_text() for f in Path("logs/workflows").glob("*.jsonl"))
    assert '"status": "resumed"' in content


def test_irrelevant_email_ignored(monkeypatch):
    monkeypatch.setattr(agent_internal_search, "internal_run", lambda t: {"payload": {}})
    monkeypatch.setattr(agent_internal_search.email_sender, "send", lambda **k: None)
    monkeypatch.setattr(agent_internal_search.email_sender, "send_email", lambda **k: None)
    monkeypatch.setattr(
        orchestrator.email_reader,
        "fetch_replies",
        lambda: [{"creator": "a@b", "task_id": "999", "fields": {"domain": "x.com"}}],
    )
    trig = _trigger({"company": "ACME", "email": "a@b", "phone": "1"})
    with pytest.raises(SystemExit):
        orchestrator.run(
            triggers=[trig],
            researchers=[agent_internal_search.run],
            pdf_renderer=_stub_pdf,
            csv_exporter=_stub_csv,
            hubspot_upsert=lambda d: None,
            hubspot_attach=lambda p, c: None,
            hubspot_check_existing=lambda cid: None,
        )
    content = "".join(f.read_text() for f in Path("logs/workflows").glob("*.jsonl"))
    assert '"status": "pending"' in content

