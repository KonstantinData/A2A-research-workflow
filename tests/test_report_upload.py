"""Tests for HubSpot report upload decision logic."""

from pathlib import Path
import datetime as dt
import sys
import json

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import orchestrator


def _dummy_trigger() -> dict:
    return {
        "source": "calendar",
        "creator": "alice@example.com",
        "recipient": "alice@example.com",
        "payload": {},
    }


@pytest.fixture
def setup_env(monkeypatch, tmp_path):
    """Prepare environment and capture log events."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "pid")
    from core import utils
    from core.utils import log_step

    utils.WORKFLOW_ID = None
    utils.SUMMARY = {}

    def fake_send_email(*a, **k):
        log_step("orchestrator", "mail_sent", {"to": k.get("to")})

    monkeypatch.setattr(orchestrator.email_sender, "send_email", fake_send_email)

    logs = []
    monkeypatch.setattr(orchestrator, "log_event", lambda rec: logs.append(rec))
    return logs


def _fake_pdf(data, path: Path) -> None:
    path.write_text("pdf")


def _fake_csv(data, path: Path) -> None:
    path.write_text("csv")


def test_upload_when_no_existing_report(setup_env, monkeypatch):
    logs = setup_env
    called = {"attach": 0}

    def fake_attach(path, cid):
        called["attach"] += 1

    orchestrator.run(
        triggers=[_dummy_trigger()],
        researchers=[],
        consolidate_fn=lambda x: {},
        pdf_renderer=_fake_pdf,
        csv_exporter=_fake_csv,
        hubspot_upsert=lambda d: "123",
        hubspot_attach=fake_attach,
        hubspot_check_existing=lambda cid: None,
        company_id="123",
    )

    assert called["attach"] == 1
    assert logs[0]["status"] == "report_uploaded"


def test_skip_when_recent_report(setup_env, monkeypatch):
    logs = setup_env
    called = {"attach": 0}
    recent = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).isoformat()

    def fake_attach(path, cid):
        called["attach"] += 1

    orchestrator.run(
        triggers=[_dummy_trigger()],
        researchers=[],
        consolidate_fn=lambda x: {},
        pdf_renderer=_fake_pdf,
        csv_exporter=_fake_csv,
        hubspot_upsert=lambda d: "123",
        hubspot_attach=fake_attach,
        hubspot_check_existing=lambda cid: {"createdAt": recent},
        company_id="123",
    )

    assert called["attach"] == 0
    assert logs[0]["status"] == "report_skipped"


def test_upload_when_old_report(setup_env, monkeypatch):
    logs = setup_env
    called = {"attach": 0}
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)).isoformat()

    def fake_attach(path, cid):
        called["attach"] += 1

    orchestrator.run(
        triggers=[_dummy_trigger()],
        researchers=[],
        consolidate_fn=lambda x: {},
        pdf_renderer=_fake_pdf,
        csv_exporter=_fake_csv,
        hubspot_upsert=lambda d: "123",
        hubspot_attach=fake_attach,
        hubspot_check_existing=lambda cid: {"createdAt": old},
        company_id="123",
    )

    assert called["attach"] == 1
    assert logs[0]["status"] == "report_uploaded"


def test_no_company_id_or_pdf(setup_env, monkeypatch):
    logs = setup_env
    called = {"attach": 0}

    def fake_attach(path, cid):
        called["attach"] += 1

    orchestrator.run(
        triggers=[_dummy_trigger()],
        researchers=[],
        consolidate_fn=lambda x: {},
        pdf_renderer=_fake_pdf,
        csv_exporter=_fake_csv,
        hubspot_upsert=lambda d: None,
        hubspot_attach=fake_attach,
        hubspot_check_existing=lambda cid: None,
        company_id=None,
    )

    assert called["attach"] == 0
    assert logs[0]["status"] == "report_sent"

    summary = json.loads((Path("logs/workflows/summary.json")).read_text())
    assert summary["mails_sent"] == 1
    assert summary["warnings"] == 0

