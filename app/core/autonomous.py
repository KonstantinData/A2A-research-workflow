"""Compatibility wrapper around the event-store orchestrator.

This module exposes an ``autonomous_orchestrator`` object matching the legacy
interface expected by the public API and CLI entry points.  The legacy
implementation in ``core.autonomous_orchestrator`` relied on an event bus and a
set of loosely coupled agents.  The new orchestrator lives in
``app.core.orchestrator`` and operates directly on the persisted event store.

To keep existing integrations working we provide a thin façade that proxies
manual trigger registration into the event store and exposes lightweight status
lookups.  The wrapper intentionally does not attempt to emulate the full agent
lifecycle; instead it focuses on durable persistence so that other migration
steps (such as ``scripts/migrate_event_ids.py``) can reason about historic
entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.events import Event
from app.core.event_store import EventStore
from app.core.id_factory import new_event_id
from app.core.logging import log_step
from app.core.orchestrator import Orchestrator
from app.core.status import EventStatus
from config.settings import SETTINGS


@dataclass
class _AgentDescriptor:
    """Placeholder describing a legacy autonomous agent."""

    name: str
    capabilities: List[str]
    enabled: bool = True
    running_tasks: int = 0


class _EmptyAgentRegistry:
    """Return an empty agent list for compatibility with the legacy API."""

    def list_agents(self) -> List[_AgentDescriptor]:
        return []


class AutonomousWorkflow:
    """Facade exposing the legacy autonomous orchestrator interface."""

    def __init__(self, *, store: Optional[EventStore] = None) -> None:
        self._store = store or EventStore()
        self._engine = Orchestrator(store=self._store)
        self._running = False
        self.agent_registry = _EmptyAgentRegistry()

    async def start(self) -> None:
        """Start processing events using the new orchestrator engine."""

        if self._running:
            return
        self._running = True
        log_step("orchestrator", "started", {"live": SETTINGS.live_mode})
        try:
            await self._engine.start()
        finally:
            self._running = False

    def stop(self) -> None:
        """Signal the orchestrator loop to stop."""

        self._running = False
        self._engine.stop()

    def process_manual_trigger(self, trigger_data: Dict[str, Any]) -> str:
        """Persist ``trigger_data`` as a new manual event and return its ID."""

        payload = dict(trigger_data or {})
        event_id = payload.get("event_id") or new_event_id()
        now = datetime.now(timezone.utc)
        event = Event(
            event_id=event_id,
            type="ManualTriggerReceived",
            created_at=now,
            updated_at=now,
            status=EventStatus.PENDING,
            payload=payload,
            labels=["manual"],
            correlation_id=payload.get("correlation_id"),
        )
        self._store.create_event(event)
        log_step(
            "orchestrator",
            "manual_trigger_recorded",
            {"event_id": event_id, "source": payload.get("source", "manual")},
        )
        return event_id

    def get_workflow_status(self, event_id: str) -> Dict[str, Any]:
        """Return a simplified status dictionary for ``event_id``."""

        event = self._store.get(event_id)
        if event is None:
            return {"status": "not_found"}
        return {
            "status": event.status.value,
            "last_update": event.updated_at.isoformat(),
            "event_count": 1,
        }


# Public singleton mirroring the legacy module level instance
autonomous_orchestrator = AutonomousWorkflow()

__all__ = ["AutonomousWorkflow", "autonomous_orchestrator"]
