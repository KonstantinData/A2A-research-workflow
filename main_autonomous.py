#!/usr/bin/env python3
"""Main entry point for autonomous A2A workflow."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.autonomous_orchestrator import autonomous_orchestrator
from core.utils import log_step


async def main():
    """Run the autonomous orchestrator."""
    try:
        log_step("main", "starting_autonomous_mode", {})
        await autonomous_orchestrator.start()
    except KeyboardInterrupt:
        log_step("main", "shutdown_requested", {})
        autonomous_orchestrator.stop()
    except Exception as e:
        log_step("main", "startup_error", {"error": str(e)}, severity="critical")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())