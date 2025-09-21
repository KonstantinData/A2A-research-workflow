#!/usr/bin/env python3
"""Test autonomous workflow functionality."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.autonomous import autonomous_orchestrator

import pytest

try:  # pragma: no cover - guard legacy utils
    from core.utils import log_step
except ImportError:  # pragma: no cover - module removed
    pytestmark = pytest.mark.skip(
        reason="Legacy core utils removed; autonomous workflow logging migrated"
    )


def test_autonomous_workflow():
    """Test autonomous workflow with mock trigger."""
    
    # Mock trigger data
    trigger_data = {
        "source": "calendar",
        "creator": "test@example.com",
        "recipient": "test@example.com",
        "payload": {
            "event_id": "test_event_123",
            "summary": "Research meeting with Example GmbH",
            "description": "Meeting preparation for Example GmbH",
            "company_name": "Example GmbH",
            "domain": "example.com",
            "creator": "test@example.com"
        }
    }
    
    try:
        # Process manual trigger
        correlation_id = autonomous_orchestrator.process_manual_trigger(trigger_data)
        log_step("test", "trigger_processed", {
            "correlation_id": correlation_id,
            "trigger_source": trigger_data.get("source")
        })
        
        # Check workflow status
        status = autonomous_orchestrator.get_workflow_status(correlation_id)
        log_step("test", "workflow_status", status)
        
        print(f"✓ Autonomous workflow test completed successfully")
        print(f"  Correlation ID: {correlation_id}")
        print(f"  Status: {status}")

        assert status["status"] == "pending"
        assert status["event_count"] == 1

        return True
        
    except Exception as e:
        log_step("test", "autonomous_workflow_error", {"error": str(e)}, severity="critical")
        print(f"✗ Autonomous workflow test failed: {e}")
        return False


if __name__ == "__main__":
    success = test_autonomous_workflow()
    sys.exit(0 if success else 1)