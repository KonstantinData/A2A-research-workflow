"""FastAPI interface for autonomous workflow management."""

from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # Fallback classes for when FastAPI is not available
    class FastAPI:
        def __init__(self, *args, **kwargs): pass
        def get(self, *args, **kwargs): return lambda f: f
        def post(self, *args, **kwargs): return lambda f: f
    
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            self.status_code = status_code
            self.detail = detail

from app.core.autonomous import autonomous_orchestrator
from core.event_bus import event_bus


class TriggerRequest(BaseModel):
    company_name: Optional[str] = None
    domain: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    creator: Optional[str] = None


class WorkflowStatus(BaseModel):
    correlation_id: str
    status: str
    last_update: str
    event_count: int


app = FastAPI(title="A2A Autonomous Workflow API", version="1.0.0")


@app.get("/")
async def root():
    """API health check."""
    return {"message": "A2A Autonomous Workflow API", "status": "running"}


@app.post("/trigger", response_model=Dict[str, str])
async def create_trigger(request: TriggerRequest):
    """Create a new workflow trigger."""
    trigger_data = {
        "company_name": request.company_name,
        "domain": request.domain,
        "summary": request.summary,
        "description": request.description,
        "creator": request.creator,
        "event_id": f"manual_{datetime.now().isoformat()}"
    }
    
    correlation_id = autonomous_orchestrator.process_manual_trigger(trigger_data)
    
    return {
        "correlation_id": correlation_id,
        "status": "triggered",
        "message": "Workflow started"
    }


@app.get("/workflow/{correlation_id}", response_model=WorkflowStatus)
async def get_workflow_status(correlation_id: str):
    """Get workflow status by correlation ID."""
    status = autonomous_orchestrator.get_workflow_status(correlation_id)
    
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return WorkflowStatus(
        correlation_id=correlation_id,
        status=status["status"],
        last_update=status["last_update"],
        event_count=status["event_count"]
    )


@app.get("/agents")
async def list_agents():
    """List all registered agents."""
    registry = getattr(autonomous_orchestrator, "agent_registry", None)
    if not registry:
        return {"agents": []}

    agents = []
    for agent in registry.list_agents():
        # ``AutonomousWorkflow`` exposes simple descriptors to preserve the
        # legacy API contract without depending on concrete agent classes.
        if hasattr(agent, "metadata"):
            metadata = agent.metadata
            capabilities = [getattr(cap, "value", str(cap)) for cap in getattr(metadata, "capabilities", [])]
            agents.append(
                {
                    "name": getattr(metadata, "name", "unknown"),
                    "capabilities": capabilities,
                    "enabled": getattr(metadata, "enabled", True),
                    "running_tasks": len(getattr(agent, "_running_tasks", [])),
                }
            )
        else:
            agents.append(
                {
                    "name": getattr(agent, "name", "unknown"),
                    "capabilities": list(getattr(agent, "capabilities", [])),
                    "enabled": getattr(agent, "enabled", True),
                    "running_tasks": getattr(agent, "running_tasks", 0),
                }
            )

    return {"agents": agents}


@app.get("/events")
async def get_events(correlation_id: Optional[str] = None):
    """Get event history."""
    events = event_bus.get_events(correlation_id)
    
    return {
        "events": [event.to_dict() for event in events[-50:]]  # Last 50 events
    }


if __name__ == "__main__":
    if not FASTAPI_AVAILABLE:
        print("FastAPI not installed. Install with: pip install fastapi uvicorn")
        sys.exit(1)
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)