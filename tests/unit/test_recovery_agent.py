import json

import pytest

from agents import recovery_agent
from config.settings import SETTINGS

try:  # pragma: no cover - guard legacy orchestrator
    from core import orchestrator, statuses
except ImportError:  # pragma: no cover - orchestrator removed
    pytestmark = pytest.mark.skip(
        reason="Legacy orchestrator recovery hooks removed; migrate to app.core"
    )


@pytest.fixture(autouse=True)
def _reset_workflows_dir(tmp_path, monkeypatch):
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    monkeypatch.setattr(SETTINGS, "workflows_dir", workflows_dir)
    return workflows_dir


def _collect_log(monkeypatch):
    records = []
    monkeypatch.setattr(orchestrator, "log_event", lambda record: records.append(record))
    return records


def test_handle_failure_restarts_when_log_entry_exists(monkeypatch, _reset_workflows_dir):
    workflows_dir = _reset_workflows_dir
    log_file = workflows_dir / "workflow.jsonl"
    log_file.write_text(
        json.dumps({"event_id": "evt-123", "status": "processing"}) + "\n",
        encoding="utf-8",
    )

    records = _collect_log(monkeypatch)
    sent_emails = []
    monkeypatch.setattr(
        recovery_agent.email_sender,
        "send_email",
        lambda **kwargs: sent_emails.append(kwargs),
    )

    recovery_agent.handle_failure("evt-123", RuntimeError("boom"))

    assert any(r.get("status") == "restart_attempted" for r in records)
    assert not any(r.get("status") == statuses.NEEDS_ADMIN_FIX for r in records)
    assert not sent_emails


def test_handle_failure_skips_restart_for_terminal_status(monkeypatch, _reset_workflows_dir):
    workflows_dir = _reset_workflows_dir
    log_file = workflows_dir / "workflow.jsonl"
    log_file.write_text(
        json.dumps({"event_id": "evt-456", "status": statuses.REPORT_SENT}) + "\n",
        encoding="utf-8",
    )

    records = _collect_log(monkeypatch)
    sent_emails = []
    monkeypatch.setattr(
        recovery_agent.email_sender,
        "send_email",
        lambda **kwargs: sent_emails.append(kwargs),
    )

    recovery_agent.handle_failure("evt-456", RuntimeError("boom"))

    assert not any(r.get("status") == "restart_attempted" for r in records)
    assert any(r.get("status") == statuses.NEEDS_ADMIN_FIX for r in records)
    assert sent_emails
