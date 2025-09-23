from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.autonomous import autonomous_orchestrator
from app.core.event_store import EventStore, list_events
from app.core.events import Event


class TriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str | None = None
    domain: str | None = None
    summary: str | None = None
    description: str | None = None
    creator: str | None = None


class TriggerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    status: str = Field(default="triggered")
    message: str = Field(default="Workflow started")


class WorkflowStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    status: str
    last_update: datetime
    event_count: int


class EventRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    event_id: str
    type: str
    status: str
    created_at: datetime
    updated_at: datetime
    payload: dict[str, Any]
    labels: list[str] = Field(default_factory=list)
    correlation_id: str | None = None

    @field_validator("status", mode="before")
    @classmethod
    def _coerce_status(cls, value: Any) -> str:
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    @field_validator("labels", mode="before")
    @classmethod
    def _ensure_labels(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [str(value)]


app = FastAPI(title="A2A Autonomous Workflow API", version="1.0.0")


def _event_to_record(event: Event) -> EventRecord:
    return EventRecord.model_validate(event)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "A2A Autonomous Workflow API", "status": "running"}


@app.get("/healthz")
async def healthz() -> dict[str, bool]:
    """Liveness probe endpoint."""

    return {"ok": True}


@app.get("/readyz")
async def readyz() -> dict[str, bool]:
    """Readiness probe endpoint."""

    try:
        list_events(limit=1, offset=0)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=503, detail="Event store unavailable") from exc
    return {"ready": True}


@app.post("/trigger", response_model=TriggerResponse)
async def create_trigger(request: TriggerRequest) -> TriggerResponse:
    trigger_data = request.model_dump(exclude_none=True)
    correlation_id = autonomous_orchestrator.process_manual_trigger(trigger_data)
    return TriggerResponse(correlation_id=correlation_id)


@app.get("/workflow/{correlation_id}", response_model=WorkflowStatus)
async def get_workflow_status(correlation_id: str) -> WorkflowStatus:
    status = autonomous_orchestrator.get_workflow_status(correlation_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Workflow not found")
    return WorkflowStatus(
        correlation_id=correlation_id,
        status=status["status"],
        last_update=datetime.fromisoformat(status["last_update"]),
        event_count=status["event_count"],
    )


@app.get("/events", response_model=list[EventRecord])
async def get_events(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    correlation_id: str | None = Query(default=None),
) -> list[EventRecord]:
    events = list_events(limit=limit, offset=offset, correlation_id=correlation_id)
    return [_event_to_record(event) for event in events]


@app.get("/events/{event_id}", response_model=EventRecord)
async def get_event(event_id: str) -> EventRecord:
    event = EventStore.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_to_record(event)
