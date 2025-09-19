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
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create task if loop is running
                    asyncio.create_task(self.handle_event(event))
                else:
                    # Run in new loop if no loop is running
                    asyncio.run(self.handle_event(event))
            except Exception:
                # Fallback to sync processing
                import asyncio
                result = asyncio.run(self.process_event(event))
                
        self.event_bus.subscribe(EventType.FIELD_COMPLETION_REQUESTED, sync_handler)
    
    async def process_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Process field completion request."""
        # Convert event to trigger format expected by existing agent
        trigger = {
            "payload": event.payload,
            "source": "calendar"
        }
        
        # Run existing field completion logic
        result = field_completion_run(trigger)
        
        return result if result else {}