from __future__ import annotations

from typing import Any

import pytest

from config import settings as settings_module
from output import email_send
from integrations import email_sender


def _set_allowlist(monkeypatch: pytest.MonkeyPatch, domains: set[str]) -> None:
    normalised = {d.lower() for d in domains}
    monkeypatch.setattr(settings_module, "EMAIL_ALLOWLIST", normalised, raising=False)
    primary = sorted(normalised)[0] if normalised else ""
    monkeypatch.setattr(settings_module.SETTINGS, "allowlist_email_domain", primary, raising=False)


def test_email_allowed_accepts_allowlisted_domains(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_allowlist(monkeypatch, {"example.com"})

    assert settings_module.email_allowed("User@Example.com")
    assert settings_module.email_allowed("person@sub.example.com")


def test_email_allowed_rejects_unlisted_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_allowlist(monkeypatch, {"example.com"})

    assert not settings_module.email_allowed("user@other.com")
    assert not settings_module.email_allowed("invalid-address")


def test_output_send_email_enforces_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_allowlist(monkeypatch, {"example.com"})

    captured: dict[str, Any] = {}

    def fake_send_email(*, to: str, subject: str, body: str, **kwargs: Any) -> None:
        captured["to"] = to
        captured["subject"] = subject
        captured["body"] = body
        captured["kwargs"] = kwargs

    monkeypatch.setattr(email_sender, "send_email", fake_send_email)

    email_send.send_email("user@example.com", "Subject", "Body")
    assert captured["to"] == "user@example.com"

    with pytest.raises(AssertionError):
        email_send.send_email("user@other.com", "Subject", "Body")
