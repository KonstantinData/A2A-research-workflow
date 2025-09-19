"""Autonomous orchestrator using event-driven architecture."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from core.event_bus import EventBus, EventType, event_bus
from core.agent_controller import AgentRegistry, WorkflowCoordinator, agent_registry, workflow_coordinator
from agents.autonomous_field_completion_agent import AutonomousFieldCompletionAgent
from agents.autonomous_research_agent import AutonomousInternalSearchAgent, AutonomousExternalSearchAgent
from agents.autonomous_consolidation_agent import AutonomousConsolidationAgent
from agents.autonomous_report_agent import AutonomousReportAgent
from agents.autonomous_email_agent import AutonomousEmailAgent
from core.services import google_calendar_service
from core.utils import log_step


class AutonomousOrchestrator:
    """Event-driven orchestrator for autonomous workflow execution."""
    
    def __init__(self):
        self.event_bus = event_bus
        self.agent_registry = agent_registry
        self.workflow_coordinator = workflow_coordinator
        self._running = False
        
        # Initialize agents
        self._initialize_agents()
    
    def _initialize_agents(self) -> None:
        """Initialize and register autonomous agents."""
        # Field completion agent
        field_agent = AutonomousFieldCompletionAgent(self.event_bus)
        self.agent_registry.register(field_agent)
        
        # Research agents
        internal_agent = AutonomousInternalSearchAgent(self.event_bus)
        external_agent = AutonomousExternalSearchAgent(self.event_bus)
        
        # Processing agents
        consolidation_agent = AutonomousConsolidationAgent(self.event_bus)
        report_agent = AutonomousReportAgent(self.event_bus)
        email_agent = AutonomousEmailAgent(self.event_bus)
        
        # Register all agents
        self.agent_registry.register(internal_agent)
        self.agent_registry.register(external_agent)
        self.agent_registry.register(consolidation_agent)
        self.agent_registry.register(report_agent)
        self.agent_registry.register(email_agent)
        
        log_step("autonomous_orchestrator", "agents_initialized", {
            "agent_count": len(self.agent_registry.list_agents()),
            "agents": [agent.metadata.name for agent in self.agent_registry.list_agents()]
        })
    
    async def start(self) -> None:
        """Start the autonomous orchestrator."""
        self._running = True
        log_step("autonomous_orchestrator", "started", {})
        
        # Start trigger monitoring
        asyncio.create_task(self._monitor_triggers())
        
        # Keep running
        while self._running:
            await asyncio.sleep(1)
    
    def stop(self) -> None:
        """Stop the orchestrator."""
        self._running = False
        log_step("autonomous_orchestrator", "stopped", {})
    
    async def _monitor_triggers(self) -> None:
        """Monitor for new triggers and publish events."""
        while self._running:
            try:
                # Fetch calendar events
                events = google_calendar_service.fetch_events()
                
                for event in events:
                    # Convert to trigger format
                    trigger_payload = {
                        "event_id": event.get("id"),
                        "summary": event.get("summary"),
                        "description": event.get("description"),
                        "creator": event.get("creator", {}).get("email"),
                        "start": event.get("start", {}).get("dateTime"),
                        "end": event.get("end", {}).get("dateTime"),
                        "attendees": event.get("attendees", [])
                    }
                    
                    # Publish trigger event
                    self.event_bus.publish(
                        EventType.TRIGGER_RECEIVED,
                        trigger_payload,
                        source_agent="trigger_monitor"
                    )
                
                # Wait before next poll
                await asyncio.sleep(60)  # Poll every minute
                
            except Exception as e:
                log_step("autonomous_orchestrator", "trigger_monitor_error", {
                    "error": str(e)
                }, severity="error")
                await asyncio.sleep(30)  # Wait before retry
    
    def process_manual_trigger(self, trigger_data: Dict[str, Any]) -> str:
        """Process a manual trigger and return correlation ID."""
        correlation_id = self.event_bus.publish(
            EventType.TRIGGER_RECEIVED,
            trigger_data,
            source_agent="manual_trigger"
        )
        return correlation_id
    
    def get_workflow_status(self, correlation_id: str) -> Dict[str, Any]:
        """Get status of a workflow by correlation ID."""
        events = self.event_bus.get_events(correlation_id)
        
        if not events:
            return {"status": "not_found"}
        
        # Determine current status from events
        latest_event = events[-1]
        
        status_map = {
            EventType.TRIGGER_RECEIVED: "triggered",
            EventType.FIELD_COMPLETION_COMPLETED: "field_completion_done",
            EventType.RESEARCH_COMPLETED: "research_in_progress",
            EventType.CONSOLIDATION_COMPLETED: "consolidation_done",
            EventType.REPORT_COMPLETED: "report_generated",
            EventType.WORKFLOW_COMPLETED: "completed",
            EventType.WORKFLOW_FAILED: "failed"
        }
        
        return {
            "status": status_map.get(latest_event.type, "unknown"),
            "last_update": latest_event.timestamp.isoformat(),
            "event_count": len(events)
        }


# Global orchestrator instance
autonomous_orchestrator = AutonomousOrchestrator()