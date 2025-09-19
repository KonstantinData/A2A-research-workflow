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

from core.autonomous_orchestrator import autonomous_orchestrator
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
    agents = autonomous_orchestrator.agent_registry.list_agents()
    
    return {
        "agents": [
            {
                "name": agent.metadata.name,
                "capabilities": [cap.value for cap in agent.metadata.capabilities],
                "enabled": agent.metadata.enabled,
                "running_tasks": len(agent._running_tasks)
            }
            for agent in agents
        ]
    }


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