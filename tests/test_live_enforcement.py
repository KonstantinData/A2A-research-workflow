import os
import pytest
import sys, pathlib

import config.env as env_module
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import core.orchestrator as orch

def test_live_guard_fails_without_env(monkeypatch):
    monkeypatch.setenv("LIVE_MODE","1")
    for k in [
        "GOOGLE_CLIENT_ID_V2",
        "GOOGLE_CLIENT_SECRET_V2",
        "GOOGLE_REFRESH_TOKEN",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASS",
        "MAIL_FROM",
        "HUBSPOT_ACCESS_TOKEN",
    ]:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(Exception):
        orch._assert_live_ready()


def test_live_guard_accepts_legacy_smtp_from(monkeypatch, caplog):
    monkeypatch.setenv("LIVE_MODE", "1")
    monkeypatch.setenv("GOOGLE_CLIENT_ID_V2", "client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET_V2", "secret")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "refresh")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASS", "password")
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "token")
    monkeypatch.delenv("MAIL_FROM", raising=False)
    monkeypatch.setenv("SMTP_FROM", "legacy@example.com")
    monkeypatch.setattr(env_module, "_warned_smtp_from", False)

    with caplog.at_level("WARNING", logger="config.env"):
        orch._assert_live_ready()

    assert os.getenv("MAIL_FROM") == "legacy@example.com"
    assert any("SMTP_FROM is deprecated" in rec.message for rec in caplog.records)
