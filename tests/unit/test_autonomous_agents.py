import asyncio
from datetime import datetime, timezone

from core.agent_controller import AgentRegistry, WorkflowCoordinator
from core.event_bus import Event, EventBus, EventType
from agents.autonomous_research_agent import AutonomousInternalSearchAgent
from agents.autonomous_email_agent import AutonomousEmailAgent
from agents import agent_internal_search
from integrations import email_sender


def test_workflow_coordinator_extracts_payload_and_metadata():
    bus = EventBus()
    registry = AgentRegistry()
    coordinator = WorkflowCoordinator(registry, bus)

    captured = []
    bus.subscribe(EventType.FIELD_COMPLETION_REQUESTED, lambda event: captured.append(event))

    trigger_payload = {
        "source": "calendar",
        "creator": "owner@example.com",
        "recipient": "owner@example.com",
        "payload": {
            "event_id": "evt1",
            "summary": "Intro call",
        },
    }

    bus.publish(EventType.TRIGGER_RECEIVED, trigger_payload)

    assert captured, "Field completion request was not published"
    event = captured[0]
    assert event.payload["event_id"] == "evt1"
    assert event.payload["summary"] == "Intro call"
    assert event.payload["creator"] == "owner@example.com"
    state = next(iter(coordinator._active_workflows.values()))
    assert state["metadata"]["creator"] == "owner@example.com"
    assert state["metadata"]["recipient"] == "owner@example.com"


def test_workflow_coordinator_missing_fields_requests_email():
    bus = EventBus()
    registry = AgentRegistry()
    coordinator = WorkflowCoordinator(registry, bus)

    email_events = []
    bus.subscribe(EventType.EMAIL_REQUESTED, lambda event: email_events.append(event))

    trigger_payload = {
        "source": "calendar",
        "creator": "owner@example.com",
        "recipient": "owner@example.com",
        "payload": {
            "event_id": "evt2",
            "summary": "Needs data",
        },
    }

    correlation_id = bus.publish(EventType.TRIGGER_RECEIVED, trigger_payload)

    fc_event = Event(
        id="fc",
        type=EventType.FIELD_COMPLETION_COMPLETED,
        payload={},
        timestamp=datetime.now(timezone.utc),
        correlation_id=correlation_id,
    )
    coordinator._handle_field_completion(fc_event)

    assert email_events, "Missing fields email was not requested"
    email_event = email_events[0]
    payload = email_event.payload
    assert payload["missing"] == ["company_name", "domain"]
    assert payload["payload"]["creator"] == "owner@example.com"
    assert payload["metadata"]["creator"] == "owner@example.com"


def test_autonomous_internal_search_agent_unwraps_payload(monkeypatch):
    bus = EventBus()
    agent = AutonomousInternalSearchAgent(bus)

    captured = {}

    def _run(trigger):
        captured["trigger"] = trigger
        return {"status": "ok"}

    monkeypatch.setattr(agent_internal_search, "run", _run)

    payload = {
        "event_id": "evt3",
        "company_name": "ACME",
        "creator": "owner@example.com",
    }
    event = Event(
        id="research",
        type=EventType.RESEARCH_REQUESTED,
        payload=payload,
        timestamp=datetime.now(timezone.utc),
    )

    asyncio.run(agent.process_event(event))

    trigger = captured["trigger"]
    assert trigger["payload"] is payload
    assert trigger["source"] == "calendar"
    assert trigger["creator"] == "owner@example.com"


def test_autonomous_email_agent_missing_fields_uses_metadata(monkeypatch):
    bus = EventBus()
    agent = AutonomousEmailAgent(bus)

    sent = []

    def _send_email(**kwargs):
        sent.append(kwargs)

    monkeypatch.setattr(email_sender, "send_email", _send_email)

    payload = {"event_id": "evt4"}
    metadata = {"creator": None, "recipient": "fallback@example.com"}
    event = Event(
        id="email",
        type=EventType.EMAIL_REQUESTED,
        payload={
            "type": "missing_fields",
            "payload": payload,
            "missing": ["domain"],
            "metadata": metadata,
        },
        timestamp=datetime.now(timezone.utc),
    )

    asyncio.run(agent.process_event(event))

    assert sent, "Email was not sent"
    assert sent[0]["to"] == "fallback@example.com"
