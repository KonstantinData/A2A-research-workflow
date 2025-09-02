import pytest
from pathlib import Path

from core import orchestrator
from agents import recovery_agent


def test_main_handles_string_exit(monkeypatch):
    def fake_run():
        raise SystemExit("No real calendar events detected – aborting run")

    monkeypatch.setattr(orchestrator, "run", fake_run)
    monkeypatch.setattr(orchestrator, "build_user_credentials", lambda scopes: object())
    monkeypatch.setenv("LIVE_MODE", "0")
    rc = orchestrator.main([])
    assert rc == 0


def test_abort_cleans_temp_and_logs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    records = []
    monkeypatch.setattr(orchestrator, "log_event", lambda r: records.append(r))
    tmp = Path("artifacts") / "42"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "data.json").write_text("x", encoding="utf-8")

    recovery_agent.abort("42")

    assert not tmp.exists()
    assert any(r.get("status") == "aborted" and r.get("event_id") == "42" for r in records)


def test_run_logs_resumed_on_restart(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(orchestrator, "finalize_summary", lambda: None)
    monkeypatch.setattr(orchestrator, "bundle_logs_into_exports", lambda: None)
    monkeypatch.setattr(orchestrator.reminder_service, "check_and_notify", lambda t: None)
    monkeypatch.setattr(orchestrator.field_completion_agent, "run", lambda t: {})
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)
    monkeypatch.setattr(orchestrator.email_reader, "fetch_replies", lambda: [])
    monkeypatch.setattr(orchestrator, "_missing_required", lambda s, p: [])
    monkeypatch.setattr(orchestrator, "extract_company", lambda x: None)
    monkeypatch.setattr(orchestrator, "extract_domain", lambda x: None)

    records = []
    monkeypatch.setattr(orchestrator, "log_event", lambda r: records.append(r))

    trig = [{"payload": {"event_id": "42", "company_name": "Acme", "domain": "acme.com"}}]

    orchestrator.run(
        triggers=trig,
        researchers=[],
        pdf_renderer=lambda d, p: None,
        csv_exporter=lambda d, p: None,
        hubspot_upsert=lambda d: None,
        hubspot_attach=lambda p, c: None,
        hubspot_check_existing=lambda c: None,
        duplicate_checker=lambda d, e: False,
        company_id=None,
        restart_event_id="42",
    )

    assert any(r.get("status") == "resumed" and r.get("event_id") == "42" for r in records)
