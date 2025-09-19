"""Agent controller for autonomous workflow management."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set
from enum import Enum

from core.event_bus import EventBus, Event, EventType, event_bus
from core.utils import log_step


class AgentCapability(Enum):
    FIELD_COMPLETION = "field_completion"
    INTERNAL_SEARCH = "internal_search"
    EXTERNAL_SEARCH = "external_search"
    CONSOLIDATION = "consolidation"
    REPORT_GENERATION = "report_generation"
    EMAIL_COMMUNICATION = "email_communication"
    HUBSPOT_INTEGRATION = "hubspot_integration"


@dataclass
class AgentMetadata:
    name: str
    capabilities: Set[AgentCapability]
    priority: int = 0
    max_concurrent: int = 1
    enabled: bool = True


class BaseAgent(ABC):
    """Base class for autonomous agents."""
    
    def __init__(self, metadata: AgentMetadata, event_bus: EventBus):
        self.metadata = metadata
        self.event_bus = event_bus
        self._running_tasks: Set[str] = set()
        self._register_handlers()
    
    @abstractmethod
    def _register_handlers(self) -> None:
        """Register event handlers for this agent."""
        pass
    
    @abstractmethod
    async def process_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Process an event and return result payload."""
        pass
    
    def can_handle(self, event: Event) -> bool:
        """Check if agent can handle the event."""
        if not self.metadata.enabled:
            return False
        if len(self._running_tasks) >= self.metadata.max_concurrent:
            return False
        return True
    
    async def handle_event(self, event: Event) -> None:
        """Handle an event with error handling and logging."""
        if not self.can_handle(event):
            return
            
        correlation_id = event.correlation_id or event.id
        self._running_tasks.add(correlation_id)
        
        try:
            log_step(self.metadata.name, "processing_event", {
                "event_id": event.id,
                "event_type": event.type.value,
                "correlation_id": correlation_id
            })
            
            result = await self.process_event(event)
            
            if result:
                # Publish completion event
                completion_type = self._get_completion_event_type(event.type)
                if completion_type:
                    self.event_bus.publish(
                        completion_type,
                        result,
                        source_agent=self.metadata.name,
                        correlation_id=correlation_id
                    )
            
        except Exception as e:
            log_step(self.metadata.name, "processing_error", {
                "event_id": event.id,
                "error": str(e),
                "correlation_id": correlation_id
            }, severity="error")
            
            # Publish failure event
            self.event_bus.publish(
                EventType.WORKFLOW_FAILED,
                {"error": str(e), "failed_agent": self.metadata.name},
                source_agent=self.metadata.name,
                correlation_id=correlation_id
            )
        finally:
            self._running_tasks.discard(correlation_id)
    
    def _get_completion_event_type(self, request_type: EventType) -> Optional[EventType]:
        """Map request event types to completion event types."""
        mapping = {
            EventType.FIELD_COMPLETION_REQUESTED: EventType.FIELD_COMPLETION_COMPLETED,
            EventType.RESEARCH_REQUESTED: EventType.RESEARCH_COMPLETED,
            EventType.CONSOLIDATION_REQUESTED: EventType.CONSOLIDATION_COMPLETED,
            EventType.REPORT_REQUESTED: EventType.REPORT_COMPLETED,
            EventType.EMAIL_REQUESTED: EventType.EMAIL_SENT,
        }
        return mapping.get(request_type)


class AgentRegistry:
    """Registry for managing autonomous agents."""
    
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._capabilities: Dict[AgentCapability, List[str]] = {}
    
    def register(self, agent: BaseAgent) -> None:
        """Register an agent."""
        self._agents[agent.metadata.name] = agent
        
        # Update capability index
        for capability in agent.metadata.capabilities:
            if capability not in self._capabilities:
                self._capabilities[capability] = []
            self._capabilities[capability].append(agent.metadata.name)
        
        log_step("agent_registry", "agent_registered", {
            "agent_name": agent.metadata.name,
            "capabilities": [c.value for c in agent.metadata.capabilities]
        })
    
    def get_agents_by_capability(self, capability: AgentCapability) -> List[BaseAgent]:
        """Get agents that have a specific capability."""
        agent_names = self._capabilities.get(capability, [])
        return [self._agents[name] for name in agent_names if self._agents[name].metadata.enabled]
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Get agent by name."""
        return self._agents.get(name)
    
    def list_agents(self) -> List[BaseAgent]:
        """List all registered agents."""
        return list(self._agents.values())


class WorkflowCoordinator:
    """Coordinates workflow execution across autonomous agents."""
    
    def __init__(self, agent_registry: AgentRegistry, event_bus: EventBus):
        self.registry = agent_registry
        self.event_bus = event_bus
        self._active_workflows: Dict[str, Dict[str, Any]] = {}
        
        # Subscribe to workflow events
        self.event_bus.subscribe(EventType.TRIGGER_RECEIVED, self._handle_trigger)
        self.event_bus.subscribe(EventType.FIELD_COMPLETION_COMPLETED, self._handle_field_completion)
        self.event_bus.subscribe(EventType.RESEARCH_COMPLETED, self._handle_research_completion)
        self.event_bus.subscribe(EventType.CONSOLIDATION_COMPLETED, self._handle_consolidation_completion)
        self.event_bus.subscribe(EventType.REPORT_COMPLETED, self._handle_report_completion)
        self.event_bus.subscribe(EventType.WORKFLOW_FAILED, self._handle_workflow_failure)
    
    def _handle_trigger(self, event: Event) -> None:
        """Handle new trigger events."""
        correlation_id = event.correlation_id or event.id
        
        # Initialize workflow state
        self._active_workflows[correlation_id] = {
            "status": "field_completion",
            "payload": event.payload,
            "completed_stages": set()
        }
        
        # Request field completion
        self.event_bus.publish(
            EventType.FIELD_COMPLETION_REQUESTED,
            event.payload,
            correlation_id=correlation_id
        )
    
    def _handle_field_completion(self, event: Event) -> None:
        """Handle field completion results."""
        correlation_id = event.correlation_id
        if not correlation_id or correlation_id not in self._active_workflows:
            return
        
        workflow = self._active_workflows[correlation_id]
        workflow["payload"].update(event.payload)
        workflow["completed_stages"].add("field_completion")
        
        # Check if we have required fields
        payload = workflow["payload"]
        if payload.get("company_name") and payload.get("domain"):
            # Request research
            workflow["status"] = "research"
            self.event_bus.publish(
                EventType.RESEARCH_REQUESTED,
                payload,
                correlation_id=correlation_id
            )
        else:
            # Request human input via email
            self.event_bus.publish(
                EventType.EMAIL_REQUESTED,
                {
                    "type": "missing_fields",
                    "payload": payload,
                    "missing": ["company_name", "domain"]
                },
                correlation_id=correlation_id
            )
    
    def _handle_research_completion(self, event: Event) -> None:
        """Handle research completion."""
        correlation_id = event.correlation_id
        if not correlation_id or correlation_id not in self._active_workflows:
            return
        
        workflow = self._active_workflows[correlation_id]
        workflow["completed_stages"].add("research")
        
        # Collect all research results
        if "research_results" not in workflow:
            workflow["research_results"] = []
        workflow["research_results"].append(event.payload)
        
        # Check if all research agents have completed
        research_agents = self.registry.get_agents_by_capability(AgentCapability.INTERNAL_SEARCH)
        research_agents.extend(self.registry.get_agents_by_capability(AgentCapability.EXTERNAL_SEARCH))
        
        if len(workflow["research_results"]) >= len(research_agents):
            # Request consolidation
            workflow["status"] = "consolidation"
            self.event_bus.publish(
                EventType.CONSOLIDATION_REQUESTED,
                {
                    "results": workflow["research_results"],
                    "original_payload": workflow["payload"]
                },
                correlation_id=correlation_id
            )
    
    def _handle_consolidation_completion(self, event: Event) -> None:
        """Handle consolidation completion."""
        correlation_id = event.correlation_id
        if not correlation_id or correlation_id not in self._active_workflows:
            return
        
        workflow = self._active_workflows[correlation_id]
        workflow["consolidated_data"] = event.payload
        workflow["completed_stages"].add("consolidation")
        workflow["status"] = "report_generation"
        
        # Request report generation
        self.event_bus.publish(
            EventType.REPORT_REQUESTED,
            event.payload,
            correlation_id=correlation_id
        )
    
    def _handle_report_completion(self, event: Event) -> None:
        """Handle report generation completion."""
        correlation_id = event.correlation_id
        if not correlation_id or correlation_id not in self._active_workflows:
            return
        
        workflow = self._active_workflows[correlation_id]
        workflow["completed_stages"].add("report_generation")
        workflow["status"] = "completed"
        
        # Publish workflow completion
        self.event_bus.publish(
            EventType.WORKFLOW_COMPLETED,
            {
                "consolidated_data": workflow.get("consolidated_data"),
                "report_paths": event.payload
            },
            correlation_id=correlation_id
        )
        
        # Clean up workflow state
        del self._active_workflows[correlation_id]
    
    def _handle_workflow_failure(self, event: Event) -> None:
        """Handle workflow failures."""
        correlation_id = event.correlation_id
        if correlation_id and correlation_id in self._active_workflows:
            del self._active_workflows[correlation_id]
        
        log_step("workflow_coordinator", "workflow_failed", {
            "correlation_id": correlation_id,
            "error": event.payload.get("error"),
            "failed_agent": event.payload.get("failed_agent")
        }, severity="error")


# Global instances
agent_registry = AgentRegistry()
workflow_coordinator = WorkflowCoordinator(agent_registry, event_bus)