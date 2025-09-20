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
        import html
        
        missing_fields = payload.get("missing", [])
        original_payload = payload.get("payload", {})

        # Get recipient from original payload
        fallback_recipient = "support@a2a-research.com"
        recipient = (
            original_payload.get("creator")
            or original_payload.get("recipient")
            or fallback_recipient
        )

        # Extract context information
        raw_task_id = (
            payload.get("task_id")
            or original_payload.get("task_id")
        )
        raw_event_id = (
            original_payload.get("event_id")
            or payload.get("event_id")
        )
        event_title = (
            original_payload.get("summary")
            or original_payload.get("title")
            or "Research Request"
        )
        company_name = original_payload.get("company_name") or "Unknown Company"

        def _normalise_identifier(value: Any) -> str:
            if value is None:
                return ""
            text = str(value).strip()
            return text

        task_id_value = _normalise_identifier(raw_task_id)
        event_id_value = _normalise_identifier(raw_event_id)

        # Escape HTML to prevent XSS
        safe_fields = []
        for field in missing_fields:
            text = str(field).strip()
            if not text:
                continue
            safe_fields.append(html.escape(text))
        safe_event_title = html.escape(str(event_title))
        safe_company_name = html.escape(str(company_name))
        safe_task_id = html.escape(task_id_value) if task_id_value else ""
        safe_event_id = html.escape(event_id_value) if event_id_value else ""

        subject_base = "Missing Information Required - A2A Research"
        subject = (
            f"{subject_base} (Task: {task_id_value})"
            if task_id_value
            else subject_base
        )

        body_lines = [
            "Hello,",
            "",
            "We need additional information to complete the research for your request:",
            "",
            f"Event: {safe_event_title}",
            f"Company: {safe_company_name}",
            f"Task ID: {safe_task_id or '(not provided)'}",
            f"Event ID: {safe_event_id or '(not provided)'}",
            "",
        ]

        if safe_fields:
            body_lines.append("Missing fields:")
            body_lines.extend(f"- {field}" for field in safe_fields)
        else:
            body_lines.append("Missing fields: (not specified)")

        body_lines.extend(
            [
                "",
                "Please provide the missing information by replying to this email.",
                "",
                "Best regards,",
                "A2A Research Team",
            ]
        )

        body = "\n".join(body_lines)

        send_kwargs = {}
        if task_id_value:
            send_kwargs["task_id"] = task_id_value
        if event_id_value:
            send_kwargs["event_id"] = event_id_value

        try:
            send_email(recipient, subject, body, **send_kwargs)
            return {"status": "sent", "recipient": recipient}
        except Exception as e:
            from core.utils import log_step
            log_step("email_agent", "send_error", {"error": str(e)}, severity="error")
            return {"status": "failed", "error": str(e)}

    
    async def _handle_report_email(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle report delivery email."""
        fallback_recipient = "support@a2a-research.com"
        recipient = payload.get("recipient", fallback_recipient)
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