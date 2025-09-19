"""Autonomous email communication agent."""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.agent_controller import BaseAgent, AgentMetadata, AgentCapability
from core.event_bus import EventBus, Event, EventType
from integrations import email_sender


class AutonomousEmailAgent(BaseAgent):
    """Autonomous email communication agent."""
    
    def __init__(self, event_bus: EventBus):
        metadata = AgentMetadata(
            name="email_agent",
            capabilities={AgentCapability.EMAIL_COMMUNICATION},
            priority=6,
            max_concurrent=3
        )
        super().__init__(metadata, event_bus)
    
    def _register_handlers(self) -> None:
        """Register event handlers."""
        def sync_handler(event):
            import asyncio
            try:
                asyncio.create_task(self.handle_event(event))
            except Exception:
                asyncio.run(self.handle_event(event))
        self.event_bus.subscribe(EventType.EMAIL_REQUESTED, sync_handler)
    
    async def process_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Process email request."""
        email_type = event.payload.get("type")
        payload = event.payload.get("payload", {})
        
        if email_type == "missing_fields":
            return await self._handle_missing_fields_email(payload, event.payload.get("missing", []))
        elif email_type == "report":
            return await self._handle_report_email(payload, event.payload.get("attachments", []))
        
        return {}
    
    async def _handle_missing_fields_email(self, payload: Dict[str, Any], missing: list) -> Dict[str, Any]:
        """Send missing fields request email."""
        creator_email = payload.get("creator") or payload.get("creatorEmail")
        if not creator_email:
            return {"error": "No creator email found"}
        
        try:
            email_sender.send_email(
                to=creator_email,
                subject="Missing information for research",
                body=f"Please provide: {', '.join(missing)}",
                task_id=payload.get("event_id")
            )
            return {"sent": True, "to": creator_email}
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_report_email(self, payload: Dict[str, Any], attachments: list) -> Dict[str, Any]:
        """Send report email."""
        recipient = payload.get("creator") or payload.get("recipient")
        if not recipient:
            return {"error": "No recipient found"}
        
        try:
            email_sender.send_email(
                to=recipient,
                subject="Your A2A research report",
                body="Please find the attached report.",
                attachments=attachments
            )
            return {"sent": True, "to": recipient}
        except Exception as e:
            return {"error": str(e)}