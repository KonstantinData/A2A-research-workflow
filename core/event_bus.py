"""Legacy event bus removed in favour of the event store backed orchestrator."""
from __future__ import annotations

raise ImportError(
    "core.event_bus has been removed. Use app.core.bus or app.core.orchestrator integrations instead."
)
