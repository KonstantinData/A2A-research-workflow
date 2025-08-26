"""Tests for orchestrator guard behaviour and normal run."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import orchestrator


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

    called = {"pdf": 0, "csv": 0}

    def fake_pdf(data, path):
        called["pdf"] += 1

    def fake_csv(data, path):
        called["csv"] += 1

    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)

    with pytest.raises(SystemExit) as exc:
        orchestrator.run(pdf_renderer=fake_pdf, csv_exporter=fake_csv)

    assert exc.value.code == 0
    assert called == {"pdf": 0, "csv": 0}

    log_dir = Path("logs/workflows")
    files = list(log_dir.glob("*_workflow.jsonl"))
    assert files, "log file not written"
    content = files[0].read_text()
    assert '"status": "no_triggers"' in content


def test_run_processes_with_triggers(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)

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
