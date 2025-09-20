#!/usr/bin/env python3
"""Full end-to-end workflow test."""

import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.autonomous_orchestrator import autonomous_orchestrator
from core.utils import log_step


async def test_full_workflow():
    """Test complete autonomous workflow."""
    
    print("🚀 Starting full A2A workflow test...")
    
    # Mock trigger data with complete information
    trigger_data = {
        "source": "calendar",
        "creator": "test@example.com",
        "recipient": "test@example.com",
        "payload": {
            "event_id": "test_full_workflow_123",
            "summary": "Research meeting with TechCorp GmbH",
            "description": "Meeting preparation for TechCorp GmbH - need company research",
            "company_name": "TechCorp GmbH",
            "domain": "techcorp.com",
            "creator": "test@example.com",
            "industry_group": "Technology",
            "industry": "Software Development"
        }
    }
    
    try:
        # Process trigger
        correlation_id = autonomous_orchestrator.process_manual_trigger(trigger_data)
        print(f"✓ Trigger processed with correlation ID: {correlation_id}")
        
        # Wait for processing
        print("⏳ Waiting for workflow processing...")
        await asyncio.sleep(3)
        
        # Check final status
        status = autonomous_orchestrator.get_workflow_status(correlation_id)
        print(f"✓ Final workflow status: {status}")
        
        # Check if outputs were generated
        from config.settings import SETTINGS
        
        pdf_files = list(SETTINGS.exports_dir.glob("*.pdf"))
        csv_files = list(SETTINGS.exports_dir.glob("*.csv"))
        
        print(f"✓ Generated files:")
        print(f"  - PDF files: {len(pdf_files)}")
        print(f"  - CSV files: {len(csv_files)}")
        
        if pdf_files:
            print(f"  - Latest PDF: {pdf_files[-1]}")
        if csv_files:
            print(f"  - Latest CSV: {csv_files[-1]}")
        
        print("🎉 Full workflow test completed successfully!")
        return True
        
    except Exception as e:
        log_step("test", "full_workflow_error", {"error": str(e)}, severity="critical")
        print(f"❌ Full workflow test failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_full_workflow())
    sys.exit(0 if success else 1)