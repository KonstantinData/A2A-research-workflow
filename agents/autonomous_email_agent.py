"""Autonomous email communication agent."""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.agent_controller import BaseAgent, AgentMetadata, AgentCapability
from core.event_bus import EventBus, Event, EventType
from integrations.email_sender import send_email


class AutonomousEmailAgent(BaseAgent):
    """Autonomous email communication agent."""
    
    def __init__(self, event_bus: EventBus):
        metadata = AgentMetadata(
            name="email_agent",
            capabilities={AgentCapability.EMAIL_COMMUNICATION},
            priority=6,
            max_concurrent=2
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
        self.event_bus.subscribe(EventType.EMAIL_REQUESTED, sync_handler)
    
    async def process_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Process email request."""
        email_type = event.payload.get("type")
        
        if email_type == "missing_fields":
            return await self._handle_missing_fields_email(event.payload)
        elif email_type == "report":
            return await self._handle_report_email(event.payload)
        
        return None
    
    async def _handle_missing_fields_email(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle missing fields email request."""
        missing_fields = payload.get("missing", [])
        original_payload = payload.get("payload", {})
        
        # Get recipient from original payload
        recipient = (
            original_payload.get("creator") or
            original_payload.get("recipient") or
            "unknown@example.com"
        )
        
        subject = "Missing Information Required - A2A Research"
        body = f"""
        Hello,
        
        We need additional information to complete the research for your request:
        
        Missing fields: {', '.join(missing_fields)}
        
        Please provide the missing information by replying to this email.
        
        Best regards,
        A2A Research Team
        """
        
        try:
            send_email(recipient, subject, body)
            return {"status": "sent", "recipient": recipient}
        except Exception as e:
            from core.utils import log_step
            log_step("email_agent", "send_error", {"error": str(e)}, severity="error")
            return {"status": "failed", "error": str(e)}
    
    async def _handle_report_email(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle report delivery email."""
        recipient = payload.get("recipient", "unknown@example.com")
        pdf_path = payload.get("pdf_path")
        
        subject = "A2A Research Report Ready"
        body = """
        Hello,
        
        Your A2A research report has been generated and is attached to this email.
        
        Best regards,
        A2A Research Team
        """
        
        attachments = []
        if pdf_path:
            attachments.append(pdf_path)
        
        try:
            send_email(recipient, subject, body, attachments=attachments)
            return {"status": "sent", "recipient": recipient}
        except Exception as e:
            from core.utils import log_step
            log_step("email_agent", "send_error", {"error": str(e)}, severity="error")
            return {"status": "failed", "error": str(e)}