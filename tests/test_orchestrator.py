"""Tests for orchestrator guard behaviour and normal run."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import orchestrator
from agents import field_completion_agent, reminder_service


def _dummy_trigger():
    return {
        "source": "calendar",
        "creator": "alice@example.com",
        "recipient": "alice@example.com",
        "payload": {},
    }


def test_run_exits_when_no_triggers(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(orchestrator, "gather_triggers", lambda *a, **k: [])
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)
    res = orchestrator.run()
    assert res == {"status": "idle"}

    log_dir = Path("logs/workflows")
    files = sorted(log_dir.glob("wf-*.jsonl"))
    assert files, "log file not written"
    content = files[0].read_text()
    assert '"status": "no_triggers"' in content
    out_dir = Path("output/exports")
    assert (out_dir / "report.pdf").exists()
    assert (out_dir / "data.csv").exists()


def test_run_processes_with_triggers(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)
    monkeypatch.setenv("A2A_TEST_MODE", "1")

    called = {"pdf": 0, "csv": 0}

    def fake_pdf(data, path):
        called["pdf"] += 1
        path.write_text("pdf")

    def fake_csv(data, path):
        called["csv"] += 1
        path.write_text("csv")

    orchestrator.run(
        triggers=[_dummy_trigger()],
        researchers=[],
        consolidate_fn=lambda x: {},
        pdf_renderer=fake_pdf,
        csv_exporter=fake_csv,
        hubspot_upsert=lambda d: None,
        hubspot_attach=lambda p, c: None,
        hubspot_check_existing=lambda cid: None,
    )

    out_dir = Path("output/exports")
    assert (out_dir / "report.pdf").exists()
    assert (out_dir / "data.csv").exists()
    assert called == {"pdf": 1, "csv": 1}


def test_run_processes_event_missing_fields(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    events = [{"id": "1", "event_id": "e1", "summary": "Research meeting"}]
    monkeypatch.setattr(orchestrator, "fetch_events", lambda: events)
    monkeypatch.setattr(orchestrator, "fetch_contacts", lambda: [])
    monkeypatch.setattr(orchestrator, "_calendar_fetch_logged", lambda wf_id: True)
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)
    monkeypatch.setattr(reminder_service, "check_and_notify", lambda t: None)
    monkeypatch.setattr(field_completion_agent, "run", lambda t: {"company_name": "ACME", "domain": "acme.com"})
    monkeypatch.setenv("A2A_TEST_MODE", "1")

    triggers = orchestrator.gather_triggers()
    assert len(triggers) == 1

    orchestrator.run(
        triggers=triggers,
        researchers=[],
        consolidate_fn=lambda r: {},
        pdf_renderer=lambda data, path: path.write_text("pdf"),
        csv_exporter=lambda data, path: path.write_text("csv"),
        hubspot_upsert=lambda d: None,
        hubspot_attach=lambda p, c: None,
        hubspot_check_existing=lambda cid: None,
    )

    logs = "".join(p.read_text() for p in Path("logs/workflows").glob("*.jsonl"))
    assert '"status": "enriched_by_ai"' in logs
