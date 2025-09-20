"""Autonomous consolidation agent."""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.agent_controller import BaseAgent, AgentMetadata, AgentCapability
from core.event_bus import EventBus, Event, EventType
from core import consolidate


class AutonomousConsolidationAgent(BaseAgent):
    """Autonomous consolidation agent."""
    
    def __init__(self, event_bus: EventBus):
        metadata = AgentMetadata(
            name="consolidation_agent",
            capabilities={AgentCapability.CONSOLIDATION},
            priority=4,
            max_concurrent=1
        )
        super().__init__(metadata, event_bus)
    
    def _register_handlers(self) -> None:
        """Register event handlers."""
        def sync_handler(event):
            import asyncio
            try:
                # Run synchronously to avoid command injection via asyncio.create_task
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.handle_event(event))
                finally:
                    loop.close()
            except Exception as e:
                # Fallback - log error instead of running potentially unsafe code
                from core.utils import log_step
                log_step("consolidation_agent", "sync_handler_error", {"error": str(e)}, severity="error")
        self.event_bus.subscribe(EventType.CONSOLIDATION_REQUESTED, sync_handler)
    
    async def process_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Process consolidation request."""
        results = event.payload.get("results", [])
        
        if not results:
            return {}
        
        # Use existing consolidation logic
        consolidated = consolidate.consolidate(results)
        
        return consolidated