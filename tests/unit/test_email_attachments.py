from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import email_sender
from config import settings as settings_module


def _set_allowlist(monkeypatch: pytest.MonkeyPatch, domains: set[str]) -> None:
    normalised = {d.lower() for d in domains}
    monkeypatch.setattr(settings_module, "EMAIL_ALLOWLIST", normalised, raising=False)
    primary = sorted(normalised)[0] if normalised else ""
    monkeypatch.setattr(
        settings_module.SETTINGS,
        "allowlist_email_domain",
        primary,
        raising=False,
    )


def test_small_attachment_sent(monkeypatch, tmp_path):
    file = tmp_path / "report.pdf"
    file.write_bytes(b"x" * 1024)  # 1KB

    called = {}

    def fake_deliver(to, subject, body, attachments=None):
        called["attachments"] = attachments
        called["body"] = body

    def fake_validate(to):
        return to  # Always return the recipient as valid

    _set_allowlist(monkeypatch, {"b"})
    # Allowlist deaktivieren, sonst kehrt send_email() früh zurück
    monkeypatch.setenv("ALLOWLIST_EMAIL_DOMAIN", "")
    monkeypatch.setenv("LIVE_MODE", "0")

    monkeypatch.setenv("SMTP_HOST", "localhost")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASS", "p")
    
    # Patch SETTINGS.live_mode directly since it's already initialized
    from config.settings import SETTINGS
    monkeypatch.setattr(SETTINGS, "live_mode", 0)
    
    monkeypatch.setattr(email_sender, "_deliver", fake_deliver)
    monkeypatch.setattr(email_sender, "_validate_recipient", fake_validate)
    
    email_sender.send_email("a@b", "sub", "body", attachments=[str(file)])
    assert called["attachments"] == [str(file)]


def test_large_attachment_skipped(monkeypatch, tmp_path):
    file = tmp_path / "big.pdf"
    file.write_bytes(b"x" * (6 * 1024 * 1024))

    called = {}

    def fake_deliver(to, subject, body, attachments=None):
        called["attachments"] = attachments
        called["body"] = body

    def fake_validate(to):
        return to  # Always return the recipient as valid

    logs = []
    monkeypatch.setattr(email_sender, "log_step", lambda *a, **k: logs.append((a, k)))

    _set_allowlist(monkeypatch, {"b"})
    # Allowlist deaktivieren
    monkeypatch.setenv("ALLOWLIST_EMAIL_DOMAIN", "")
    monkeypatch.setenv("LIVE_MODE", "0")

    monkeypatch.setenv("SMTP_HOST", "localhost")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASS", "p")
    
    # Patch SETTINGS.live_mode directly since it's already initialized
    from config.settings import SETTINGS
    monkeypatch.setattr(SETTINGS, "live_mode", 0)
    
    monkeypatch.setattr(email_sender, "_deliver", fake_deliver)
    monkeypatch.setattr(email_sender, "_validate_recipient", fake_validate)
    
    email_sender.send_email("a@b", "sub", "body", attachments=[str(file)])
    assert called["attachments"] == []
    assert str(file) in called["body"]
    assert any("attachment_skipped_too_large" in a for a, _ in logs)
