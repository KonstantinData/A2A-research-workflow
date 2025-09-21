from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.autonomous import autonomous_orchestrator
from app.core.event_store import EventStore, list_events
from app.core.events import Event


class TriggerRequest(BaseModel):
    company_name: Optional[str] = None
    domain: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    creator: Optional[str] = None


class TriggerResponse(BaseModel):
    correlation_id: str
    status: str = Field(default="triggered")
    message: str = Field(default="Workflow started")


class WorkflowStatus(BaseModel):
    correlation_id: str
    status: str
    last_update: datetime
    event_count: int


class EventRecord(BaseModel):
    event_id: str
    type: str
    status: str
    created_at: datetime
    updated_at: datetime
    payload: dict[str, Any]
    labels: List[str] = Field(default_factory=list)
    correlation_id: Optional[str] = None


app = FastAPI(title="A2A Autonomous Workflow API", version="1.0.0")


def _event_to_record(event: Event) -> EventRecord:
    return EventRecord(
        event_id=event.event_id,
        type=event.type,
        status=event.status.value,
        created_at=event.created_at,
        updated_at=event.updated_at,
        payload=dict(event.payload or {}),
        labels=list(event.labels or []),
        correlation_id=event.correlation_id,
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "A2A Autonomous Workflow API", "status": "running"}


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


@app.get("/events", response_model=List[EventRecord])
async def get_events(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    correlation_id: Optional[str] = Query(default=None),
) -> List[EventRecord]:
    events = list_events(limit=limit, offset=offset, correlation_id=correlation_id)
    return [_event_to_record(event) for event in events]


@app.get("/events/{event_id}", response_model=EventRecord)
async def get_event(event_id: str) -> EventRecord:
    event = EventStore.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_to_record(event)
