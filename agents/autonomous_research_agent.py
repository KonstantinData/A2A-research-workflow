"""Autonomous research agent wrapper."""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.agent_controller import BaseAgent, AgentMetadata, AgentCapability
from core.event_bus import EventBus, Event, EventType
from agents import agent_internal_search, agent_external_level1_company_search
from agents.autonomous_utils import ensure_trigger_structure


class AutonomousInternalSearchAgent(BaseAgent):
    """Autonomous internal search agent."""
    
    def __init__(self, event_bus: EventBus):
        metadata = AgentMetadata(
            name="internal_search_agent",
            capabilities={AgentCapability.INTERNAL_SEARCH},
            priority=2,
            max_concurrent=2
        )
        super().__init__(metadata, event_bus)
    
    def _register_handlers(self) -> None:
        """Register event handlers."""
        def sync_handler(event: Event) -> None:
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.handle_event(event))
            except RuntimeError:
                asyncio.run(self.handle_event(event))
        self.event_bus.subscribe(EventType.RESEARCH_REQUESTED, sync_handler)
    
    async def process_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Process research request."""
        trigger = ensure_trigger_structure(event.payload)
        trigger.setdefault("source", "calendar")
        if isinstance(event.payload, dict):
            trigger.setdefault("creator", event.payload.get("creator"))
            trigger.setdefault("recipient", event.payload.get("recipient"))

        result = agent_internal_search.run(trigger)
        
        # Skip if missing fields
        if result.get("status") == "missing_fields":
            return None
            
        return result


class AutonomousExternalSearchAgent(BaseAgent):
    """Autonomous external search agent."""
    
    def __init__(self, event_bus: EventBus):
        metadata = AgentMetadata(
            name="external_search_agent",
            capabilities={AgentCapability.EXTERNAL_SEARCH},
            priority=3,
            max_concurrent=1
        )
        super().__init__(metadata, event_bus)
    
    def _register_handlers(self) -> None:
        """Register event handlers."""
        def sync_handler(event: Event) -> None:
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.handle_event(event))
            except RuntimeError:
                asyncio.run(self.handle_event(event))
        self.event_bus.subscribe(EventType.RESEARCH_REQUESTED, sync_handler)
    
    async def process_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Process external research request."""
        trigger = ensure_trigger_structure(event.payload)
        trigger.setdefault("source", "calendar")
        if isinstance(event.payload, dict):
            trigger.setdefault("creator", event.payload.get("creator"))
            trigger.setdefault("recipient", event.payload.get("recipient"))

        result = agent_external_level1_company_search.run(trigger)
        return result
