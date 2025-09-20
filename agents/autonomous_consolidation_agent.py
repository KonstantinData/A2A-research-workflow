"""Autonomous consolidation agent."""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.agent_controller import BaseAgent, AgentMetadata, AgentCapability
from core.event_bus import EventBus, Event, EventType
from core.consolidate import consolidate_results


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
        def sync_handler(event: Event) -> None:
            import asyncio
            import threading

            try:
                asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(self.handle_event(event))
            else:
                thread = threading.Thread(
                    target=lambda: asyncio.run(self.handle_event(event))
                )
                thread.start()
                thread.join()
        self.event_bus.subscribe(EventType.CONSOLIDATION_REQUESTED, sync_handler)
    
    async def process_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Process consolidation request."""
        results = event.payload.get("results", [])
        original_payload = event.payload.get("original_payload", {})
        
        # Consolidate all research results
        consolidated = consolidate_results(results, original_payload)
        
        return consolidated