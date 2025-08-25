import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents import agent_internal_search
from core import orchestrator


@pytest.fixture(autouse=True)
def _chdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _stub_pdf(data, path):
    path.write_text("pdf")


def _stub_csv(data, path):
    path.write_text("csv")


def _trigger(payload):
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
    payload = {
        "company": "ACME",
        "domain": "acme.com",
        "email": "a@b",
        "phone": "1",
    }
    res = agent_internal_search.run(_trigger(payload))
    assert res.get("status") != "missing_fields"
    assert send_called["rem"] == 0


def test_missing_field_triggers_reminder(monkeypatch):
    logs = []
    orig = orchestrator.log_event
    def capture(rec):
        logs.append(rec)
        orig(rec)
    monkeypatch.setattr(orchestrator, "log_event", capture)
    send_calls = []
    def fake_send(**kw):
        send_calls.append(kw)
    monkeypatch.setattr(agent_internal_search, "internal_run", lambda t: {"payload": {}})
    monkeypatch.setattr(agent_internal_search.email_sender, "send", fake_send)
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


def test_multiple_missing_fields(monkeypatch):
    captured = {}
    def fake_send(**kw):
        captured.update(kw)
    monkeypatch.setattr(agent_internal_search.email_sender, "send", fake_send)
    monkeypatch.setattr(agent_internal_search.email_sender, "send_email", lambda **k: None)
    monkeypatch.setattr(agent_internal_search, "internal_run", lambda t: {"payload": {}})
    trig = _trigger({"company": "ACME", "email": "a@b"})
    res = agent_internal_search.run(trig)
    assert res["status"] == "missing_fields"
    assert set(res["missing"]) == {"domain", "phone"}
    assert "Domain" in captured["body"] and "Phone" in captured["body"]
    assert captured["sender"] == "research-agent@condata.io"


def test_resume_after_update(monkeypatch):
    send_called = {"rem": 0}
    def fake_send(**kw):
        send_called["rem"] += 1
    called = {"internal": 0}
    def stub_internal(t):
        called["internal"] += 1
        return {"payload": {}}
    monkeypatch.setattr(agent_internal_search.email_sender, "send", fake_send)
    monkeypatch.setattr(agent_internal_search.email_sender, "send_email", lambda **k: None)
    monkeypatch.setattr(agent_internal_search, "internal_run", stub_internal)
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)
    # first run with missing domain
    trig1 = _trigger({"company": "ACME", "email": "a@b", "phone": "1"})
    with pytest.raises(SystemExit):
        orchestrator.run(
            triggers=[trig1],
            researchers=[agent_internal_search.run],
            pdf_renderer=_stub_pdf,
            csv_exporter=_stub_csv,
            hubspot_upsert=lambda d: None,
            hubspot_attach=lambda p, c: None,
            hubspot_check_existing=lambda cid: None,
        )
    assert called["internal"] == 0
    assert send_called["rem"] == 1
    # second run with all fields
    trig2 = _trigger({"company": "ACME", "domain": "acme.com", "email": "a@b", "phone": "1"})
    orchestrator.run(
        triggers=[trig2],
        researchers=[agent_internal_search.run],
        consolidate_fn=lambda x: {},
        pdf_renderer=_stub_pdf,
        csv_exporter=_stub_csv,
        hubspot_upsert=lambda d: None,
        hubspot_attach=lambda p, c: None,
        hubspot_check_existing=lambda cid: None,
    )
    assert called["internal"] == 1
    assert send_called["rem"] == 1
