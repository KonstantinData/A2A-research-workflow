from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import email_client


def test_email_client_delegates_to_email_sender(monkeypatch):
    calls = {}

    def fake_send(sender, recipient, subject, body, attachments=None):
        calls['sender'] = sender
        calls['recipient'] = recipient
        calls['subject'] = subject
        calls['body'] = body

    monkeypatch.setenv('MAIL_FROM', 'bot@example.com')
    monkeypatch.setattr(email_client.email_sender, 'send_email', fake_send)

    email_client.send_email('user@example.com', ['name', 'role'])

    assert calls['sender'] == 'bot@example.com'
    assert calls['recipient'] == 'user@example.com'
    assert 'name, role' in calls['body']
