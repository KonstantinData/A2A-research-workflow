"""Tests for parsing correlation references from inbound emails."""
from email.message import EmailMessage

from app.integrations.email_reader import _extract_event_id


def _message(subject: str = "", **headers: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    for key, value in headers.items():
        msg[key] = value
    msg.set_content("Hello")
    return msg


def test_extract_event_id_prefers_header():
    message = _message("Status [ref:IGNORED]", **{"X-Event-ID": "EVT-HEADER"})
    body = "Reference: BODY-123"
    assert _extract_event_id(message, body) == "EVT-HEADER"


def test_extract_event_id_from_subject():
    message = _message("Follow up [ref:demo-42]")
    assert _extract_event_id(message, "") == "DEMO-42"


def test_extract_event_id_ignores_malformed_subject():
    message = _message("Follow up [ref:demo 42]")
    assert _extract_event_id(message, "No usable reference") is None


def test_extract_event_id_missing_reference():
    message = _message("Quarterly update")
    assert _extract_event_id(message, "No reference here") is None

