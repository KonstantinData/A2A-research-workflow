"""Schema mapping for internal company research."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

Normalized = Dict[str, Any]
Raw = Dict[str, Any]


@dataclass
class NormalizedInternalCompany:
    """Typed representation of normalized internal company data.

    The dataclass validates the presence of mandatory top level fields as
    well as required keys within the payload.  ``creator`` and ``recipient``
    must be provided and the payload must at minimum contain a ``summary``
    field.  A :class:`ValueError` is raised when any of these requirements are
    not met.
    """

    source: str
    creator: Dict[str, Any]
    recipient: Dict[str, Any]
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
    """Map raw data to the normalized schema.

    Parameters
    ----------
    trigger:
        Normalized trigger dictionary passed from the orchestrator.
    raw:
        Unstructured data retrieved by :func:`fetch`.

    Returns
    -------
    Normalized
        Structured result following the common schema of ``source``,
        ``creator``, ``recipient`` and ``payload``.
    """
    return {
        "source": "internal_company_research",
        "creator": trigger.get("creator"),
        "recipient": trigger.get("recipient"),
        "payload": raw,
    }
