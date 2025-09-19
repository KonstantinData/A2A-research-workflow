"""Autonomous report generation agent."""

from __future__ import annotations

from typing import Any, Dict, Optional
from pathlib import Path

from core.agent_controller import BaseAgent, AgentMetadata, AgentCapability
from core.event_bus import EventBus, Event, EventType
from output import pdf_render, csv_export
from config.settings import SETTINGS


class AutonomousReportAgent(BaseAgent):
    """Autonomous report generation agent."""
    
    def __init__(self, event_bus: EventBus):
        metadata = AgentMetadata(
            name="report_agent",
            capabilities={AgentCapability.REPORT_GENERATION},
            priority=5,
            max_concurrent=2
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
        self.event_bus.subscribe(EventType.REPORT_REQUESTED, sync_handler)
    
    async def process_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Process report generation request."""
        consolidated = event.payload
        
        # Ensure output directory exists
        SETTINGS.exports_dir.mkdir(parents=True, exist_ok=True)
        
        pdf_path = SETTINGS.exports_dir / "report.pdf"
        csv_path = SETTINGS.exports_dir / "data.csv"
        
        try:
            # Generate PDF
            rows = consolidated.get("rows", [])
            fields = consolidated.get("fields", [])
            meta = consolidated.get("meta")
            
            if rows and fields:
                pdf_render.render_pdf(rows, fields, meta, pdf_path)
            
            # Generate CSV
            if rows:
                csv_export.export_csv(rows, csv_path)
            
            return {
                "pdf_path": str(pdf_path) if pdf_path.exists() else None,
                "csv_path": str(csv_path) if csv_path.exists() else None
            }
            
        except Exception as e:
            return {"error": str(e)}