import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import email_sender
from core import orchestrator


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

    expected = '[Research Agent] Missing Information – Event "Demo" on 2024-05-17, 09:00–10:00'
    assert captured['subject'] == expected

    body = captured['body']
    for field in ['Company:', 'Web domain:', 'Email:', 'Phone:']:
        assert field in body
    assert 'You might also update the calendar entry or contact record with these details.' in body


def test_send_reminder_handles_missing_title(monkeypatch):
    captured = {}

    def fake_send(*, to, subject, body, sender=None, attachments=None, task_id=None):
        captured['subject'] = subject

    monkeypatch.setattr(email_sender, 'send', fake_send)

    start = dt.datetime(2024, 5, 17, 9, 0)

    email_sender.send_reminder(
        to='user@example.com',
        creator_email='user@example.com',
        creator_name=None,
        event_id='evt456',
        event_title='',
        event_start=start,
        event_end=None,
        missing_fields=[],
    )

    subj = captured['subject']
    assert 'Untitled Event' in subj
    assert 'Unknown' not in subj
    assert '2024-05-17' in subj
    assert '09:00' in subj


def test_build_reminder_subject_matches_email_sender_logic():
    start = dt.datetime(2025, 8, 28, 12, 15)
    end = dt.datetime(2025, 8, 28, 14, 0)
    title = 'Meeting-Vorbereitung Firma Dr. Willmar Schwabe'
    subject = orchestrator.build_reminder_subject(title, start, end)
    expected = (
        '[Research Agent] Missing Information – Event '
        '"Meeting-Vorbereitung Firma Dr. Willmar Schwabe" on 2025-08-28, 12:15–14:00'
    )
    assert subject == expected
