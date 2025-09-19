#!/usr/bin/env python3
"""Test script for autonomous workflow."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.autonomous_orchestrator import autonomous_orchestrator
from core.event_bus import EventType
from core.utils import log_step


def test_autonomous_workflow():
    """Test the autonomous workflow system."""
    print("🧪 Testing Autonomous A2A Workflow...")
    
    # Check agent registration
    agents = autonomous_orchestrator.agent_registry.list_agents()
    print(f"✅ {len(agents)} agents registered:")
    for agent in agents:
        capabilities = [cap.value for cap in agent.metadata.capabilities]
        print(f"   - {agent.metadata.name}: {capabilities}")
    
    # Test manual trigger
    print("\n🚀 Testing manual trigger...")
    correlation_id = autonomous_orchestrator.process_manual_trigger({
        "company_name": "Test GmbH",
        "domain": "test.com",
        "creator": "test@example.com",
        "summary": "Meeting with Test GmbH for research"
    })
    
    print(f"✅ Workflow triggered with correlation ID: {correlation_id}")
    
    # Check workflow status
    status = autonomous_orchestrator.get_workflow_status(correlation_id)
    print(f"✅ Workflow status: {status}")
    
    # Check event history
    events = autonomous_orchestrator.event_bus.get_events(correlation_id)
    print(f"✅ {len(events)} events in history")
    
    print("\n🎉 Autonomous workflow test completed!")
    return True


if __name__ == "__main__":
    try:
        test_autonomous_workflow()
        print("\n✅ All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)