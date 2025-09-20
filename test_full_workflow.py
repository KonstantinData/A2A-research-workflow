#!/usr/bin/env python3
"""Full end-to-end workflow test matching the workflow schema."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Ensure deterministic test configuration
os.environ.setdefault("LIVE_MODE", "0")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import pytest

from config.settings import SETTINGS
from core.autonomous_orchestrator import autonomous_orchestrator
from core.event_bus import EventType

# Reflect the test configuration in the settings singleton
SETTINGS.live_mode = 0


def test_full_workflow() -> None:
    """Execute the autonomous workflow and assert the expected artefacts."""

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
            "industry": "Software Development",
        },
    }

    correlation_id = autonomous_orchestrator.process_manual_trigger(trigger_data)

    deadline = time.time() + 20
    events = []
    while time.time() < deadline:
        events = autonomous_orchestrator.event_bus.get_events(correlation_id)
        if any(event.type == EventType.WORKFLOW_COMPLETED for event in events):
            break
        time.sleep(0.2)
    else:
        pytest.fail("Workflow did not reach completion event")

    status = autonomous_orchestrator.get_workflow_status(correlation_id)
    assert status.get("status") == "completed", f"Unexpected workflow status: {status}"

    event_types = {event.type for event in events}

    for expected_type in (
        EventType.FIELD_COMPLETION_REQUESTED,
        EventType.FIELD_COMPLETION_COMPLETED,
        EventType.RESEARCH_REQUESTED,
        EventType.RESEARCH_COMPLETED,
        EventType.CONSOLIDATION_REQUESTED,
        EventType.CONSOLIDATION_COMPLETED,
        EventType.REPORT_REQUESTED,
        EventType.REPORT_COMPLETED,
        EventType.WORKFLOW_COMPLETED,
    ):
        assert expected_type in event_types, f"Missing workflow step: {expected_type.value}"

    pdf_files = sorted(SETTINGS.exports_dir.glob("*.pdf"))
    csv_files = sorted(SETTINGS.exports_dir.glob("*.csv"))

    assert pdf_files, "Expected a PDF dossier to be generated"
    assert csv_files, "Expected a CSV dossier to be generated"

    latest_pdf = pdf_files[-1]
    latest_csv = csv_files[-1]

    assert latest_pdf.stat().st_size > 0, "Generated PDF is empty"
    assert latest_csv.stat().st_size > 0, "Generated CSV is empty"


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    success = True
    try:
        test_full_workflow()
    except AssertionError:
        success = False
    sys.exit(0 if success else 1)
