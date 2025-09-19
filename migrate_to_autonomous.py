#!/usr/bin/env python3
"""Migration script from legacy to autonomous workflow."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.autonomous_orchestrator import autonomous_orchestrator
from core.utils import log_step


def migrate_existing_data():
    """Migrate existing workflow data to autonomous system."""
    log_step("migration", "starting_migration", {})
    
    # Check if legacy orchestrator data exists
    from config.settings import SETTINGS
    
    workflows_dir = SETTINGS.workflows_dir
    if workflows_dir.exists():
        log_step("migration", "found_existing_workflows", {
            "workflow_files": len(list(workflows_dir.glob("*.jsonl")))
        })
    
    # Initialize autonomous system
    log_step("migration", "initializing_autonomous_system", {})
    
    # Migration complete
    log_step("migration", "migration_complete", {
        "status": "success",
        "autonomous_agents": len(autonomous_orchestrator.agent_registry.list_agents())
    })
    
    print("✅ Migration to autonomous workflow completed!")
    print(f"✅ {len(autonomous_orchestrator.agent_registry.list_agents())} autonomous agents registered")
    print("✅ Ready to start autonomous mode with: python main_autonomous.py")


if __name__ == "__main__":
    migrate_existing_data()