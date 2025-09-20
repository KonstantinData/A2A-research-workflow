"""Autonomous report generation agent."""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.agent_controller import BaseAgent, AgentMetadata, AgentCapability
from core.event_bus import EventBus, Event, EventType
from output.pdf_render import render_pdf
from output.csv_export import export_csv
from config.settings import SETTINGS


class AutonomousReportAgent(BaseAgent):
    """Autonomous report generation agent."""
    
    def __init__(self, event_bus: EventBus):
        metadata = AgentMetadata(
            name="report_agent",
            capabilities={AgentCapability.REPORT_GENERATION},
            priority=5,
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
        self.event_bus.subscribe(EventType.REPORT_REQUESTED, sync_handler)
    
    async def process_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Process report generation request."""
        consolidated_data = event.payload
        
        # Generate PDF and CSV reports
        pdf_path = None
        csv_path = None
        
        try:
            # Generate PDF
            pdf_path = render_pdf(
                rows=[consolidated_data],
                fields=list(consolidated_data.keys()),
                meta={"title": "A2A Research Report"}
            )
            
            # Generate CSV
            csv_path = export_csv([consolidated_data])
            
        except Exception as e:
            from core.utils import log_step
            log_step("report_agent", "generation_error", {"error": str(e)}, severity="error")
            return None
        
        return {
            "pdf_path": pdf_path,
            "csv_path": csv_path,
            "data": consolidated_data
        }