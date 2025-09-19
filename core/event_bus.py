"""Event-driven message bus for agent communication."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum
import uuid

from core.utils import log_step


class EventType(Enum):
    TRIGGER_RECEIVED = "trigger_received"
    FIELD_COMPLETION_REQUESTED = "field_completion_requested"
    FIELD_COMPLETION_COMPLETED = "field_completion_completed"
    RESEARCH_REQUESTED = "research_requested"
    RESEARCH_COMPLETED = "research_completed"
    CONSOLIDATION_REQUESTED = "consolidation_requested"
    CONSOLIDATION_COMPLETED = "consolidation_completed"
    REPORT_REQUESTED = "report_requested"
    REPORT_COMPLETED = "report_completed"
    EMAIL_REQUESTED = "email_requested"
    EMAIL_SENT = "email_sent"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_COMPLETED = "workflow_completed"


@dataclass
class Event:
    id: str
    type: EventType
    payload: Dict[str, Any]
    timestamp: datetime
    source_agent: Optional[str] = None
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'type': self.type.value,
            'timestamp': self.timestamp.isoformat()
        }


class EventBus:
    """Simple in-memory event bus for agent coordination."""
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable[[Event], None]]] = {}
        self._event_history: List[Event] = []
        
    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Subscribe to events of a specific type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        
    def publish(self, event_type: EventType, payload: Dict[str, Any], 
                source_agent: Optional[str] = None, correlation_id: Optional[str] = None) -> str:
        """Publish an event to all subscribers."""
        event = Event(
            id=str(uuid.uuid4()),
            type=event_type,
            payload=payload,
            timestamp=datetime.now(timezone.utc),
            source_agent=source_agent,
            correlation_id=correlation_id
        )
        
        self._event_history.append(event)
        
        # Notify subscribers
        for handler in self._subscribers.get(event_type, []):
            try:
                # Handle both sync and async handlers
                import asyncio
                if asyncio.iscoroutinefunction(handler):
                    # Skip async handlers in sync context - they need proper async execution
                    continue
                else:
                    handler(event)
            except Exception as e:
                log_step("event_bus", "handler_error", {
                    "event_id": event.id,
                    "event_type": event_type.value,
                    "error": str(e)
                }, severity="error")
        
        log_step("event_bus", "event_published", {
            "event_id": event.id,
            "event_type": event_type.value,
            "source_agent": source_agent
        })
        
        return event.id
    
    def get_events(self, correlation_id: Optional[str] = None) -> List[Event]:
        """Get event history, optionally filtered by correlation ID."""
        if correlation_id:
            return [e for e in self._event_history if e.correlation_id == correlation_id]
        return self._event_history.copy()


# Global event bus instance
event_bus = EventBus()