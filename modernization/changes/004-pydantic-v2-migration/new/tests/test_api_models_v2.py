"""Pydantic v2 compatibility checks for workflow API models."""
from __future__ import annotations

from datetime import datetime, timezone

from api.workflow_api import EventRecord, TriggerRequest, TriggerResponse, WorkflowStatus
from app.core.events import Event
from app.core.status import EventStatus


def test_trigger_request_schema_marks_all_fields_optional() -> None:
    schema = TriggerRequest.model_json_schema()
    assert schema.get("required", []) == []
    properties = schema.get("properties", {})
    expected_fields = {"company_name", "domain", "summary", "description", "creator"}
    assert expected_fields.issubset(properties)
    for field_schema in properties.values():
        assert "type" in field_schema or "anyOf" in field_schema


def test_trigger_request_roundtrip_excludes_none() -> None:
    request = TriggerRequest(company_name="Acme", summary=None, creator="ops")
    dumped = request.model_dump(exclude_none=True)
    assert "summary" not in dumped
    rebuilt = TriggerRequest.model_validate(dumped)
    assert rebuilt.company_name == "Acme"
    assert rebuilt.creator == "ops"


def test_trigger_response_roundtrip_preserves_defaults() -> None:
    response = TriggerResponse(correlation_id="abc-123")
    dumped = response.model_dump()
    rebuilt = TriggerResponse.model_validate(dumped)
    assert rebuilt.correlation_id == "abc-123"
    assert rebuilt.status == "triggered"
    assert rebuilt.message == "Workflow started"


def test_event_record_accepts_domain_event() -> None:
    event = Event(
        event_id="evt-1",
        type="workflow.triggered",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
        status=EventStatus.COMPLETED,
        payload={"foo": "bar"},
        labels=None,
        correlation_id="corr-9",
    )

    record = EventRecord.model_validate(event)

    assert record.status == "completed"
    assert record.labels == []
    assert record.correlation_id == "corr-9"
    assert record.payload == {"foo": "bar"}


def test_workflow_status_roundtrip() -> None:
    now = datetime.now(tz=timezone.utc)
    status = WorkflowStatus(
        correlation_id="corr-42",
        status="running",
        last_update=now,
        event_count=3,
    )

    dumped = status.model_dump()
    rebuilt = WorkflowStatus.model_validate(dumped)

    assert rebuilt.model_dump() == dumped
