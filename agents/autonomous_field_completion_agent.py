"""Autonomous field completion agent."""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.agent_controller import BaseAgent, AgentMetadata, AgentCapability
from core.event_bus import EventBus, Event, EventType
from agents.field_completion_agent import run as field_completion_run


class AutonomousFieldCompletionAgent(BaseAgent):
    """Autonomous version of the field completion agent."""
    
    def __init__(self, event_bus: EventBus):
        metadata = AgentMetadata(
            name="field_completion_agent",
            capabilities={AgentCapability.FIELD_COMPLETION},
            priority=1,
            max_concurrent=3
        )
        super().__init__(metadata, event_bus)
    
    def _register_handlers(self) -> None:
        """Register event handlers."""
        # Use sync wrapper for event handling
        def sync_handler(event):
            try:
                # Run synchronously - no async needed for field completion
                result = self.process_event_sync(event)
                if result:
                    self.event_bus.publish(
                        EventType.FIELD_COMPLETION_COMPLETED,
                        result,
                        source_agent=self.metadata.name
                    )
            except Exception as e:
                from core.utils import log_step
                log_step("field_completion_agent", "sync_handler_error", {"error": str(e)}, severity="error")
                
        self.event_bus.subscribe(EventType.FIELD_COMPLETION_REQUESTED, sync_handler)
    
    async def process_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Process field completion request."""
        return self.process_event_sync(event)
    
    def process_event_sync(self, event: Event) -> Optional[Dict[str, Any]]:
        """Process field completion request synchronously."""
        # Convert event to trigger format expected by existing agent
        payload = event.payload or {}
        if isinstance(payload, dict) and isinstance(payload.get("payload"), dict):
            trigger_payload = payload["payload"]
            source = payload.get("source", "calendar")
            trigger_creator = payload.get("creator")
            trigger_recipient = payload.get("recipient")
        else:
            trigger_payload = payload if isinstance(payload, dict) else {}
            source = payload.get("source", "calendar") if isinstance(payload, dict) else "calendar"
            trigger_creator = payload.get("creator") if isinstance(payload, dict) else None
            trigger_recipient = payload.get("recipient") if isinstance(payload, dict) else None

        trigger = {
            "payload": trigger_payload,
            "source": source,
        }
        if trigger_creator is not None:
            trigger["creator"] = trigger_creator
        if trigger_recipient is not None:
            trigger["recipient"] = trigger_recipient

        # Run existing field completion logic
        result = field_completion_run(trigger)

        return result if result else {}