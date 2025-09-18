"""Workflow state management for persistence and recovery."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from config.settings import SETTINGS
from core.utils import log_step


class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class WorkflowState:
    """Workflow state for persistence."""
    workflow_id: str
    status: WorkflowStatus
    triggers: List[Dict[str, Any]]
    current_step: str
    results: List[Dict[str, Any]]
    created_at: str
    updated_at: str
    error_message: Optional[str] = None
    retry_count: int = 0


class WorkflowStateManager:
    """Manages workflow state persistence and recovery."""
    
    def __init__(self):
        self.state_dir = SETTINGS.artifacts_dir / "workflow_states"
        self.state_dir.mkdir(parents=True, exist_ok=True)
    
    def save_state(self, state: WorkflowState) -> None:
        """Save workflow state to disk."""
        state.updated_at = datetime.now(timezone.utc).isoformat()
        state_file = self.state_dir / f"{state.workflow_id}.json"
        
        try:
            with state_file.open("w", encoding="utf-8") as f:
                json.dump(asdict(state), f, indent=2, ensure_ascii=False)
            
            log_step("workflow_state", "saved", {
                "workflow_id": state.workflow_id,
                "status": state.status.value,
                "step": state.current_step
            })
        except (OSError, IOError) as e:
            log_step("workflow_state", "save_failed", {
                "workflow_id": state.workflow_id,
                "error": str(e)
            }, severity="error")
    
    def load_state(self, workflow_id: str) -> Optional[WorkflowState]:
        """Load workflow state from disk."""
        state_file = self.state_dir / f"{workflow_id}.json"
        
        if not state_file.exists():
            return None
        
        try:
            with state_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Convert status back to enum
            data["status"] = WorkflowStatus(data["status"])
            
            log_step("workflow_state", "loaded", {
                "workflow_id": workflow_id,
                "status": data["status"].value
            })
            
            return WorkflowState(**data)
        except (OSError, IOError, json.JSONDecodeError, ValueError) as e:
            log_step("workflow_state", "load_failed", {
                "workflow_id": workflow_id,
                "error": str(e)
            }, severity="error")
            return None
    
    def list_pending_workflows(self) -> List[str]:
        """List workflow IDs that are pending or paused."""
        pending = []
        
        for state_file in self.state_dir.glob("*.json"):
            try:
                with state_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                
                status = WorkflowStatus(data["status"])
                if status in (WorkflowStatus.PENDING, WorkflowStatus.PAUSED):
                    pending.append(data["workflow_id"])
            except (OSError, IOError, json.JSONDecodeError, ValueError):
                continue
        
        return pending
    
    def cleanup_completed(self, max_age_days: int = 7) -> None:
        """Clean up completed workflow states older than max_age_days."""
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_days * 24 * 3600)
        cleaned = 0
        
        for state_file in self.state_dir.glob("*.json"):
            try:
                if state_file.stat().st_mtime < cutoff:
                    with state_file.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    status = WorkflowStatus(data["status"])
                    if status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED):
                        state_file.unlink()
                        cleaned += 1
            except (OSError, IOError, json.JSONDecodeError, ValueError):
                continue
        
        if cleaned > 0:
            log_step("workflow_state", "cleanup", {"cleaned_count": cleaned})


# Global state manager instance
workflow_state_manager = WorkflowStateManager()