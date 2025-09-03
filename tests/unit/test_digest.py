from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents import digest
import integrations.email_sender as email_sender


def test_send_daily_admin_digest_builds_body(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    summary = {
        "workflow_id": "wf-123",
        "errors": 2,
        "warnings": 1,
        "reports_generated": 3,
        "mails_sent": 5,
        "artifact_health": {
            "pdf_ok": True,
            "pdf_size": 123,
            "csv_ok": True,
            "csv_rows": 10,
            "empty_run": False,
        },
    }
    summary_path = Path("logs/workflows")
    summary_path.mkdir(parents=True)
    (summary_path / "summary.json").write_text(json.dumps(summary))

    captured = {}

    def fake_send_email(*, to, subject, body):
        captured["to"] = to
        captured["subject"] = subject
        captured["body"] = body

    monkeypatch.setattr(email_sender, "send_email", fake_send_email)

    digest.send_daily_admin_digest("admin@example.com")

    assert captured["to"] == "admin@example.com"
    assert captured["subject"] == "A2A daily digest"
    expected = (
        "workflow_id: wf-123\n"
        "errors: 2  warnings: 1\n"
        "reports_generated: 3  mails_sent: 5\n"
        "pdf_ok: True  pdf_size: 123\n"
        "csv_ok: True  csv_rows: 10  empty_run: False"
    )
    assert captured["body"] == expected


def test_send_daily_admin_digest_no_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    called = {"flag": False}

    def fake_send_email(*, to, subject, body):
        called["flag"] = True

    monkeypatch.setattr(email_sender, "send_email", fake_send_email)

    digest.send_daily_admin_digest("admin@example.com")

    assert called["flag"] is False
