"""Synthetic demo events for demo mode only."""
from __future__ import annotations

import os
from typing import Any, Dict, List


def demo_events() -> List[Dict[str, Any]]:
    """Return synthetic events used solely for demonstration.

    The module should only be imported when ``DEMO_MODE`` or ``A2A_DEMO`` is
    enabled.  It is safe to call ``demo_events`` regardless of the environment;
    it will return an empty list if demo mode is disabled.
    """

    if os.getenv("DEMO_MODE") != "1" and os.getenv("A2A_DEMO") != "1":
        return []

    return [
        {
            "event_id": "e1",
            "summary": "Demo research event",
            "description": "",
            "start": None,
            "end": None,
            "creatorEmail": "demo@example.com",
            "creator": {"email": "demo@example.com"},
        }
    ]
