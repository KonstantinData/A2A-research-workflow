from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations import email_sender, mailer


def test_send_email_blocked_by_allowlist(monkeypatch):
    monkeypatch.setenv("ALLOWLIST_EMAIL_DOMAIN", "example.com")

    deliveries: list[tuple] = []
    monkeypatch.setattr(email_sender, "_deliver", lambda *a, **k: deliveries.append((a, k)))

    logs: list[tuple] = []
    monkeypatch.setattr(email_sender, "log_step", lambda *a, **k: logs.append((a, k)))

    email_sender.send_email("person@other.com", "subject", "body")

    assert deliveries == []
    assert any(args[1] == "email_skipped_invalid_domain" for args, _ in logs)


def test_mailer_blocks_non_allowlisted_domain(monkeypatch):
    called = False

    class DummySMTP:
        def __init__(self, *_, **__):
            nonlocal called
            called = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, *_):
            raise AssertionError("login should not be called when blocked")

        def sendmail(self, *_):
            raise AssertionError("sendmail should not be called when blocked")

    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", DummySMTP)

    with pytest.raises(ValueError):
        mailer.send_email(
            host="smtp.example.com",
            port=465,
            user="user",
            password="pass",
            mail_from="sender@example.com",
            to="recipient@unauthorised.com",
            subject="Subject",
            body="Body",
            allowed_domain="example.com",
        )

    assert not called


def test_mailer_allows_allowlisted_domain(monkeypatch):
    sent: dict[str, object] = {}

    class DummySMTP:
        def __init__(self, *_, **__):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, user, password):
            sent["login"] = (user, password)

        def sendmail(self, mail_from, recipients, message):
            sent["mail_from"] = mail_from
            sent["recipients"] = recipients
            sent["message"] = message

    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", DummySMTP)
    monkeypatch.setattr(mailer.ssl, "create_default_context", lambda: None)

    mailer.send_email(
        host="smtp.example.com",
        port=465,
        user="user",
        password="pass",
        mail_from="sender@example.com",
        to=" Recipient@Example.com ",
        subject="Subject",
        body="Body",
        allowed_domain="example.com",
    )

    assert sent["recipients"] == ["Recipient@Example.com"]
    assert sent["mail_from"] == "sender@example.com"
    assert "Subject" in sent["message"]
