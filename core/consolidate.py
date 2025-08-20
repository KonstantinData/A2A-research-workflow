"""Consolidate results produced by individual research agents.

The real project would merge a complex nested structure following the
``company.core.schema.json`` definition.  For the purposes of this exercise we
only need a light‑weight merger that records which agent supplied which piece of
information and when it was collected.  Each agent is expected to return a
dictionary where top level keys are field names and the special key ``source``
identifies the agent.

Example input::

    [
        {"source": "agent1", "legal_name": "Acme GmbH"},
        {"source": "agent2", "employees": 120},
    ]

Output::

    {
        "legal_name": {"value": "Acme GmbH", "source": "agent1",
                       "last_verified_at": "..."},
        "employees": {"value": 120, "source": "agent2",
                       "last_verified_at": "..."},
    }
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Iterable


def consolidate(results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple agent result dictionaries.

    Parameters
    ----------
    results:
        Iterable of dictionaries produced by agents.  Each dictionary should
        contain a ``source`` key and any number of field/value pairs.

    Returns
    -------
    dict
        A dictionary where every field is expanded into a structure containing
        the value, the original source and a ``last_verified_at`` timestamp.
    """

    consolidated: Dict[str, Any] = {}
    timestamp = dt.datetime.utcnow().isoformat()
    for result in results:
        source = result.get("source", "unknown")
        for key, value in result.items():
            if key == "source" or value in (None, ""):
                continue
            consolidated[key] = {
                "value": value,
                "source": source,
                "last_verified_at": timestamp,
            }
    return consolidated


__all__ = ["consolidate"]

