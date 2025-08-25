# agents/internal_company/normalize.py
"""Schema mapping for internal company research (LIVE)."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict

Normalized = Dict[str, Any]
Raw = Dict[str, Any]


@dataclass
class NormalizedInternalCompany:
    source: str
    creator: Any
    recipient: Any
    payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        missing = []
        if not self.creator:
            missing.append("creator")
        if not self.recipient:
            missing.append("recipient")
        if not self.payload:
            missing.append("payload")
        if missing:
            raise ValueError(f"Missing mandatory fields: {', '.join(missing)}")
        if "summary" not in self.payload:
            raise ValueError("Missing mandatory payload field: summary")


def normalize(trigger: Normalized, raw: Raw) -> Normalized:
    """
    Structured result following the common schema and carrying meta fields from fetch():
      exists, company_id, company_name, company_domain, last_report_date, last_report_id, neighbors
    """
    result = {
        "source": "internal_company_research",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": dict(raw),
    }
    # ensure summary exists even if upstream changed
    result["payload"].setdefault("summary", "internal company research")
    # dataclass validation
    _ = NormalizedInternalCompany(**result)
    return result
