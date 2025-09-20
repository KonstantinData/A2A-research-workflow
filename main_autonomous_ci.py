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
        
        # Use proper trigger detection with trigger words
        from core.triggers import gather_calendar_triggers
        
        triggers = gather_calendar_triggers()
        log_step("main", "triggers_detected", {"count": len(triggers)})
        
        # Process each trigger
        for trigger in triggers:
            correlation_id = autonomous_orchestrator.process_manual_trigger(trigger)
            log_step("main", "trigger_processed", {
                "correlation_id": correlation_id,
                "trigger_source": trigger.get("source")
            })
        
        # Wait a bit for processing
        await asyncio.sleep(5)
        
        log_step("main", "autonomous_ci_completed", {
            "triggers_processed": len(triggers)
        })
        
    except Exception as e:
        log_step("main", "autonomous_ci_error", {"error": str(e)}, severity="critical")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_once())