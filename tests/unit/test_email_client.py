import logging
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import email_client
import config.env as env_module


def test_email_client_delegates_to_email_sender(monkeypatch):
    calls = {}

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
        calls['sender'] = sender
        calls['recipient'] = to
        calls['subject'] = subject
        calls['body'] = body

    monkeypatch.setenv('MAIL_FROM', 'bot@example.com')
    monkeypatch.setattr(email_client.email_sender, 'send_email', fake_send)

    email_client.send_email('user@example.com', ['name', 'role'])

    assert calls['recipient'] == 'user@example.com'
    assert '- name' in calls['body']
    assert '- role' in calls['body']


def test_mail_from_falls_back_to_smtp_from(monkeypatch, caplog):
    monkeypatch.delenv('MAIL_FROM', raising=False)
    monkeypatch.setenv('SMTP_FROM', 'legacy@example.com')
    monkeypatch.setattr(env_module, '_warned_smtp_from', False)

    with caplog.at_level(logging.WARNING, logger='config.env'):
        value = email_client._mail_from()

    assert value == 'legacy@example.com'
    assert os.getenv('MAIL_FROM') == 'legacy@example.com'
    assert any('SMTP_FROM is deprecated' in record.message for record in caplog.records)
