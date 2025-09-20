"""Unit tests for :mod:`agents.autonomous_email_agent`."""

from __future__ import annotations

import asyncio


def test_missing_fields_email_without_task_id(monkeypatch):
    from agents.autonomous_email_agent import AutonomousEmailAgent
    from core.event_bus import EventBus

    bus = EventBus()
    agent = AutonomousEmailAgent(bus)

    send_calls = {}

    def fake_send_email(recipient, subject, body, **kwargs):  # noqa: ANN001 - signature matches production helper
        send_calls["recipient"] = recipient
        send_calls["subject"] = subject
        send_calls["body"] = body
        send_calls["kwargs"] = kwargs

    monkeypatch.setattr("agents.autonomous_email_agent.send_email", fake_send_email)

    payload = {
        "missing": ["company_name", " contact_email "],
        "payload": {
            "summary": "Research Request",
            "company_name": "Hartmetall-Werkzeugfabrik",
            "event_id": "evt-42",
            "creator": "employee@example.com",
        },
    }

    result = asyncio.run(agent._handle_missing_fields_email(payload))

    assert result == {"status": "sent", "recipient": "employee@example.com"}
    assert send_calls["recipient"] == "employee@example.com"
    assert send_calls["subject"] == "Missing Information Required - A2A Research"

    body = send_calls["body"]
    assert "Task ID: (not provided)" in body
    assert "Event ID: evt-42" in body
    assert "Missing fields:" in body
    assert "- company_name" in body
    assert "- contact_email" in body

    # Correlation data should include only the available identifiers
    assert send_calls["kwargs"] == {"event_id": "evt-42"}

def test_missing_fields_email_with_task_id_and_html(monkeypatch):
    from agents.autonomous_email_agent import AutonomousEmailAgent
    from core.event_bus import EventBus

    bus = EventBus()
    agent = AutonomousEmailAgent(bus)

    captured = {}

    def fake_send_email(recipient, subject, body, **kwargs):  # noqa: ANN001 - signature matches production helper
        captured["recipient"] = recipient
        captured["subject"] = subject
        captured["body"] = body
        captured["kwargs"] = kwargs

    monkeypatch.setattr("agents.autonomous_email_agent.send_email", fake_send_email)

    payload = {
        "task_id": "task-77",
        "missing": ["website"],
        "payload": {
            "summary": "Research <Request>",
            "company_name": "Example & Co.",
            "event_id": "evt-99",
            "creator": "owner@example.com",
        },
    }

    asyncio.run(agent._handle_missing_fields_email(payload))

    assert captured["subject"] == "Missing Information Required - A2A Research (Task: task-77)"
    body = captured["body"]
    assert "Event: Research &lt;Request&gt;" in body
    assert "Company: Example &amp; Co." in body
    assert "Task ID: task-77" in body
    assert "Event ID: evt-99" in body
    assert body.count("- website") == 1

    assert captured["kwargs"] == {"task_id": "task-77", "event_id": "evt-99"}
