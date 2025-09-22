from __future__ import annotations

import importlib

import pytest

from config.env import ensure_mail_from
from config.settings import Settings, SETTINGS


def test_core_modules_raise_import_error():
    with pytest.raises(ImportError) as exc:
        importlib.import_module("core.orchestrator")
    assert "app.core.orchestrator" in str(exc.value)

    with pytest.raises(ImportError) as exc_bus:
        importlib.import_module("core.event_bus")
    assert "app.core" in str(exc_bus.value)

    with pytest.raises(ImportError) as exc_logging:
        importlib.import_module("core.logging")
    assert "app.core" in str(exc_logging.value)


def test_ensure_mail_from_prefers_config(monkeypatch):
    monkeypatch.setattr(SETTINGS, "mail_from", "configured@example.com")
    monkeypatch.setattr(SETTINGS, "smtp_user", "smtp@example.com")
    assert ensure_mail_from() == "configured@example.com"


def test_ensure_mail_from_falls_back_to_smtp_user(monkeypatch):
    monkeypatch.setattr(SETTINGS, "mail_from", "")
    monkeypatch.setattr(SETTINGS, "smtp_user", "smtp@example.com")
    assert ensure_mail_from() == "smtp@example.com"


def test_settings_aliases_resolve(monkeypatch):
    monkeypatch.delenv("MAIL_FROM", raising=False)
    monkeypatch.setenv("SMTP_FROM", "alias@example.com")
    fresh = Settings()
    assert fresh.mail_from == "alias@example.com"
