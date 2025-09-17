from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import email_sender


def test_small_attachment_sent(monkeypatch, tmp_path):
    file = tmp_path / "report.pdf"
    file.write_bytes(b"x" * 1024)  # 1KB

    called = {}

    def fake_deliver(to, subject, body, attachments=None):
        called["attachments"] = attachments
        called["body"] = body

    # Allowlist deaktivieren, sonst kehrt send_email() früh zurück
    monkeypatch.setenv("ALLOWLIST_EMAIL_DOMAIN", "")

    monkeypatch.setenv("SMTP_HOST", "localhost")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASS", "p")
    monkeypatch.setattr(email_sender, "_deliver", fake_deliver)

    email_sender.send_email("a@b", "sub", "body", attachments=[str(file)])
    assert called["attachments"] == [str(file)]


def test_large_attachment_skipped(monkeypatch, tmp_path):
    file = tmp_path / "big.pdf"
    file.write_bytes(b"x" * (6 * 1024 * 1024))

    called = {}

    def fake_deliver(to, subject, body, attachments=None):
        called["attachments"] = attachments
        called["body"] = body

    logs = []
    monkeypatch.setattr(email_sender, "log_step", lambda *a, **k: logs.append((a, k)))

    # Allowlist deaktivieren
    monkeypatch.setenv("ALLOWLIST_EMAIL_DOMAIN", "")

    monkeypatch.setenv("SMTP_HOST", "localhost")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASS", "p")
    monkeypatch.setattr(email_sender, "_deliver", fake_deliver)

    email_sender.send_email("a@b", "sub", "body", attachments=[str(file)])
    assert called["attachments"] == []
    assert str(file) in called["body"]
    assert any("attachment_skipped_too_large" in a for a, _ in logs)
