#!/usr/bin/env python3
"""CI version of autonomous A2A workflow - runs once then exits."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.autonomous_orchestrator import autonomous_orchestrator
from core.services import google_calendar_service
from core.utils import log_step


async def run_once():
    """Run autonomous workflow once for CI."""
    try:
        log_step("main", "starting_autonomous_ci_mode", {})
        
        # Fetch events once
        events = google_calendar_service.fetch_events()
        log_step("main", "events_fetched", {"count": len(events)})
        
        # Process each event
        for event in events:
            trigger_payload = {
                "event_id": event.get("id"),
                "summary": event.get("summary"),
                "description": event.get("description"),
                "creator": event.get("creator", {}).get("email"),
                "start": event.get("start", {}).get("dateTime"),
                "end": event.get("end", {}).get("dateTime"),
                "attendees": event.get("attendees", [])
            }
            
            # Process trigger
            correlation_id = autonomous_orchestrator.process_manual_trigger(trigger_payload)
            log_step("main", "trigger_processed", {
                "correlation_id": correlation_id,
                "event_id": event.get("id")
            })
        
        # Wait a bit for processing
        await asyncio.sleep(5)
        
        log_step("main", "autonomous_ci_completed", {
            "events_processed": len(events)
        })
        
    except Exception as e:
        log_step("main", "autonomous_ci_error", {"error": str(e)}, severity="critical")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_once())