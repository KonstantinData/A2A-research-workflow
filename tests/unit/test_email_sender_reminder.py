import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import email_sender


def test_send_reminder_formats_subject_and_body(monkeypatch):
    captured = {}

    def fake_send(*, to, subject, body, sender=None, attachments=None, task_id=None):
        captured['subject'] = subject
        captured['body'] = body

    monkeypatch.setattr(email_sender, 'send', fake_send)

    start = dt.datetime(2024, 5, 17, 9, 0)
    end = dt.datetime(2024, 5, 17, 10, 0)

    email_sender.send_reminder(
        to='user@example.com',
        creator_email='user@example.com',
        creator_name='Alice',
        event_id='evt123',
        event_title='Demo',
        event_start=start,
        event_end=end,
        missing_fields=['Company', 'Web domain'],
    )

    assert 'Demo' in captured['subject']
    assert '2024-05-17' in captured['subject']
    assert '09:00–10:00' in captured['subject']
    assert 'Unknown' not in captured['subject']
    assert '_' not in captured['subject']

    body = captured['body']
    for field in ['Company:', 'Web domain:', 'Email:', 'Phone:']:
        assert field in body
    assert 'You might also update the calendar entry or contact record with these details.' in body
    assert 'Unknown' not in body
