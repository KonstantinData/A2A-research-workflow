"""Detail research agent placeholder."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from integrations import hubspot_api

Normalized = Dict[str, Any]


def run(trigger: Normalized) -> Normalized:
    """Stub detail research agent.

    Parameters
    ----------
    trigger: Normalized
        Normalized trigger dictionary.
    """
    # In real implementation, generate PDF/CSV and attach to HubSpot.
    payload = trigger.get("payload", {})
    report_path = payload.get("report_path")
    company_id = payload.get("company_id")
    if report_path and company_id:
        hubspot_api.attach_pdf(Path(report_path), company_id)
    return {
        "source": "company_detail_research",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": {"action": "DETAIL_REPORT_READY"},
    }
