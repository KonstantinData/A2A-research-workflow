from pathlib import Path

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

try:  # pragma: no cover - guard legacy orchestrator
    from core import orchestrator  # type: ignore
except ImportError:  # pragma: no cover - orchestrator removed
    pytestmark = pytest.mark.skip(
        reason="Legacy orchestrator logging removed; severity handled in app.core"
    )
else:
    from config.settings import SETTINGS


def test_log_event_severity_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    orchestrator.log_event({"status": "ok"})
    files = list(SETTINGS.workflows_dir.glob("*.jsonl"))
    content = files[0].read_text()
    assert '"severity": "info"' in content

    orchestrator.log_event({"status": "fail", "severity": "critical"})
    files = sorted(SETTINGS.workflows_dir.glob("*.jsonl"))
    content = files[-1].read_text()
    assert '"severity": "critical"' in content


def test_upload_failure_logged_critical(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    trig = {
        "source": "calendar",
        "creator": "a@example.com",
        "recipient": "a@example.com",
        "payload": {
            "company": "ACME",
            "domain": "acme.com",
            "email": "a@example.com",
            "phone": "1",
        },
    }

    def stub_pdf(data, path):
        path.write_text("pdf")

    def stub_csv(data, path):
        path.write_text("csv")

    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda **k: None)
    def fail_attach(path, cid):
        raise Exception("boom")

    orchestrator.run(
        triggers=[trig],
        pdf_renderer=stub_pdf,
        csv_exporter=stub_csv,
        hubspot_upsert=lambda d: 1,
        hubspot_attach=fail_attach,
    )

    content = "".join(p.read_text() for p in SETTINGS.workflows_dir.glob("*.jsonl"))
    assert '"status": "report_upload_failed"' in content
    assert '"severity": "critical"' in content
