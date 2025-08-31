import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
from integrations import email_sender


def test_request_missing_fields_sends_email(monkeypatch):
    captured = {}

    def fake_send_email(to, subject, body):
        captured["to"] = to
        captured["subject"] = subject
        captured["body"] = body

    monkeypatch.setattr(email_sender, "send_email", fake_send_email)

    task = {"id": "123"}
    missing = ["company_name", "domain"]
    recipient = "employee@example.com"

    email_sender.request_missing_fields(task, missing, recipient)

    assert captured["to"] == recipient
    assert "company_name" in captured["body"]
    assert "domain" in captured["body"]
    assert "Task ID: 123" in captured["body"]
    assert "Could you provide a few missing details" in captured["subject"]
