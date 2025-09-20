"""Autonomous report generation agent."""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.agent_controller import BaseAgent, AgentMetadata, AgentCapability
from core.event_bus import EventBus, Event, EventType
from output.pdf_render import render_pdf
from output.csv_export import export_csv, DEFAULT_FIELDS
from config.settings import SETTINGS


PLACEHOLDER = "—"


def _normalise_row(consolidated_data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a CSV/PDF ready row from consolidated workflow data."""

    field_aliases = {
        "company_name": ["company", "name"],
        "domain": ["company_domain", "website", "url"],
        "industry": ["industry_group", "sector"],
        "contact_name": ["contact", "contact_person", "primary_contact"],
        "contact_email": ["contact_email_address", "email", "creatorEmail"],
        "source": ["origin", "data_source"],
        "confidence": ["confidence_score", "score"],
        "notes": ["description", "summary", "insights"],
    }

    normalised: Dict[str, Any] = {}
    for field in DEFAULT_FIELDS:
        value = None
        candidates = [field] + field_aliases.get(field, [])
        for candidate in candidates:
            if candidate in consolidated_data:
                candidate_value = consolidated_data.get(candidate)
                if candidate_value not in (None, ""):
                    value = candidate_value
                    break
        normalised[field] = value if value not in (None, "") else PLACEHOLDER
    return normalised


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
        consolidated_data = event.payload if isinstance(event.payload, dict) else {}
        
        normalised_row = _normalise_row(consolidated_data or {})

        # Generate PDF and CSV reports
        pdf_path = None
        csv_path = None

        meta = dict(consolidated_data.get("meta") or {}) if isinstance(consolidated_data, dict) else {}
        for key in ("event_id", "task_id"):
            if key in consolidated_data and key not in meta:
                meta[key] = consolidated_data[key]
        meta.setdefault("title", "A2A Research Report")

        try:
            pdf_path = render_pdf(
                rows=[normalised_row],
                fields=list(DEFAULT_FIELDS),
                meta=meta,
            )

            csv_path = export_csv([normalised_row])

        except Exception as e:
            from core.utils import log_step
            log_step("report_agent", "generation_error", {"error": str(e)}, severity="error")
            return None

        return {
            "pdf_path": pdf_path,
            "csv_path": csv_path,
            "data": consolidated_data,
            "row": normalised_row,
        }
