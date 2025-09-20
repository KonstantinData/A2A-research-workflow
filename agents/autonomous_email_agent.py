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
        data = event.payload or {}
        email_type = data.get("type")
        payload = data.get("payload", {})
        metadata = data.get("metadata") or {}

        if email_type == "missing_fields":
            return await self._handle_missing_fields_email(payload, data.get("missing", []), metadata)
        elif email_type == "report":
            return await self._handle_report_email(payload, data.get("attachments", []), metadata)

        return {}

    def _resolve_email(self, candidate: Any) -> Optional[str]:
        if isinstance(candidate, str):
            candidate = candidate.strip()
            return candidate or None
        if isinstance(candidate, dict):
            for key in ("email", "address", "value"):
                value = candidate.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def _find_creator_email(
        self, payload: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Optional[str]:
        candidates = [
            payload.get("creatorEmail"),
            payload.get("creator_email"),
            payload.get("creator"),
            metadata.get("creator"),
            payload.get("organizerEmail"),
            payload.get("organizer_email"),
            payload.get("organizer"),
            metadata.get("recipient"),
        ]
        for candidate in candidates:
            email = self._resolve_email(candidate)
            if email:
                return email
        return None

    def _find_report_recipient(
        self, payload: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Optional[str]:
        candidates = [
            payload.get("recipient"),
            metadata.get("recipient"),
            payload.get("creator"),
            payload.get("creatorEmail"),
            metadata.get("creator"),
            payload.get("organizerEmail"),
            payload.get("organizer"),
        ]
        for candidate in candidates:
            email = self._resolve_email(candidate)
            if email:
                return email
        return None

    async def _handle_missing_fields_email(
        self, payload: Dict[str, Any], missing: list, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send missing fields request email."""
        creator_email = self._find_creator_email(payload, metadata)
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
    
    async def _handle_report_email(
        self, payload: Dict[str, Any], attachments: list, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send report email."""
        recipient = self._find_report_recipient(payload, metadata)
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