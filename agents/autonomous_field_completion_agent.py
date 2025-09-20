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
                # Safe async execution without command injection risk
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.handle_event(event))
                finally:
                    loop.close()
            except Exception as e:
                # Log error instead of running potentially unsafe code
                from core.utils import log_step
                log_step("field_completion_agent", "sync_handler_error", {"error": str(e)}, severity="error")
                
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