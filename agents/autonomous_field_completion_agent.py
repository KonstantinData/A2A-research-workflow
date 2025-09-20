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

        def sync_handler(event: Event) -> None:
            """Execute the async handler in synchronous contexts."""
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

        self.event_bus.subscribe(EventType.FIELD_COMPLETION_REQUESTED, sync_handler)

    async def process_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Process field completion request."""
        return self._process_event_sync(event)

    def _process_event_sync(self, event: Event) -> Optional[Dict[str, Any]]:
        """Process field completion request synchronously."""
        # Convert event to trigger format expected by existing agent
        trigger = {
            "payload": event.payload,
            "source": "calendar"
        }

        # Run existing field completion logic
        result = field_completion_run(trigger) or {}

        payload = event.payload or {}
        nested_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}

        for key in ("company_name", "domain", "industry_group", "industry", "creator"):
            if key not in result and key in payload:
                result[key] = payload[key]
            elif key not in result and key in nested_payload:
                result[key] = nested_payload[key]

        return result