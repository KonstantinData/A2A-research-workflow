import datetime as dt
import sys
from pathlib import Path

import pytest

# Projekt-Root in den Pfad aufnehmen
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


def test_send_reminder_formats_subject_and_body(monkeypatch):
    captured = {}

    def fake_send(
        *,
        to,
        subject,
        body,
        sender=None,
        attachments=None,
        task_id=None,
        event_id=None,
    ):
        captured["subject"] = subject
        captured["body"] = body

    _set_allowlist(monkeypatch, {"condata.io"})
    # Allowlist passend zur Empfängeradresse setzen, damit send_reminder() nicht frühzeitig abbricht
    monkeypatch.setenv("ALLOWLIST_EMAIL_DOMAIN", "condata.io")

    # send() wird von send_reminder() aufgerufen -> dieses Ziel patchen
    monkeypatch.setattr(email_sender, "send", fake_send)

    start = dt.datetime(2024, 5, 17, 9, 0)
    end = dt.datetime(2024, 5, 17, 10, 0)

    email_sender.send_reminder(
        to="user@condata.io",
        creator_email="user@condata.io",
        creator_name="Alice",
        event_id="evt123",
        event_title="Team Sync",
        event_start=start,
        event_end=end,
        missing_fields=["Company", "Web domain"],
    )

    # Subject-Checks
    assert "Team Sync" in captured["subject"]
    assert "2024-05-17" in captured["subject"]
    assert "09:00–10:00" in captured["subject"]
    assert "Unknown" not in captured["subject"]
    assert "_" not in captured["subject"]

    # Body-Checks
    body = captured["body"]
    for field in ["Company:", "Web domain:", "Email:", "Phone:"]:
        assert field in body
    assert (
        "You might also update the calendar entry or contact record with these details."
        in body
    )
    assert "Unknown" not in body
