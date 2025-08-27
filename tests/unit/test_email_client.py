from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import email_client


def test_email_client_delegates_to_email_sender(monkeypatch):
    calls = {}

    def fake_send(*, to, subject, body, sender=None, attachments=None, task_id=None):
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
