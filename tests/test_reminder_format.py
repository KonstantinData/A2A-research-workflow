from integrations import email_sender, google_calendar


def test_reminder_includes_title(monkeypatch):
    sent = {}
    monkeypatch.setattr(email_sender, "send", lambda **kw: sent.update(kw))
    trigger = {
        "creator": "a@b",
        "creator_name": "Alice",
        "event_title": "Meeting-Vorbereitung Firma Dr. Willmar Schwabe",
        "start_iso": "2025-01-01T10:00:00+00:00",
        "end_iso": "2025-01-01T11:00:00+00:00",
        "timezone": "UTC",
        "event_id": "1",
    }
    email_sender.send_reminder(trigger=trigger, missing_fields=["company", "domain"])
    assert trigger["event_title"] in sent["body"]


def test_reminder_greeting_fallback(monkeypatch):
    sent = {}
    monkeypatch.setattr(email_sender, "send", lambda **kw: sent.update(kw))
    trigger = {
        "creator": "a@b",
        "event_title": "Title",
        "start_iso": "2025-01-01T10:00:00+00:00",
        "end_iso": "2025-01-01T11:00:00+00:00",
        "timezone": "UTC",
        "event_id": "1",
    }
    email_sender.send_reminder(trigger=trigger, missing_fields=["company"])
    assert sent["body"].startswith("Hi there,")


def test_two_events_send_two_reminders(monkeypatch):
    events = [
        {
            "id": "1",
            "iCalUID": "1",
            "updated": "u1",
            "summary": "Meet Alpha",
            "start": {"dateTime": "2025-01-01T10:00:00Z"},
            "end": {"dateTime": "2025-01-01T11:00:00Z"},
            "creator": {"email": "a@b"},
        },
        {
            "id": "2",
            "iCalUID": "2",
            "updated": "u2",
            "summary": "Meet Beta",
            "start": {"dateTime": "2025-01-02T10:00:00Z"},
            "end": {"dateTime": "2025-01-02T11:00:00Z"},
            "creator": {"email": "c@d"},
        },
    ]

    class FakeReq:
        def events(self):
            return self

        def list(self, **kw):
            return self

        def execute(self):
            return {"items": events}

    monkeypatch.setattr(google_calendar, "_service", lambda: FakeReq())
    monkeypatch.setattr(google_calendar, "load_trigger_words", lambda: ["Meet"])
    monkeypatch.setattr(google_calendar, "already_processed", lambda *a, **k: False)
    monkeypatch.setattr(google_calendar, "mark_processed", lambda *a, **k: None)
    send_calls = []
    monkeypatch.setattr(
        google_calendar.email_sender, "send_reminder", lambda trigger, missing_fields: send_calls.append(trigger)
    )

    res = google_calendar.fetch_events(minutes_back=0, minutes_forward=60)
    assert len(res) == 2
    assert len(send_calls) == 2
