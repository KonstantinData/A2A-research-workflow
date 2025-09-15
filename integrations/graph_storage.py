"""Prototype graph storage integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from config.settings import SETTINGS


def store_result(result: Dict[str, Any], path: str | None = None) -> None:
    """Store a normalized run result into a simple graph structure.

    Parameters
    ----------
    result:
        Normalized result produced by an agent ``run`` function.
    path:
        Optional output path for the serialized graph. Defaults to
        ``output/graph.json``.
    """
    graph = _result_to_graph(result)
    output = Path(path) if path else SETTINGS.output_dir / "graph.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        json.dump(graph, fh, ensure_ascii=False, indent=2)


def _result_to_graph(result: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Convert a result dictionary into node and edge collections."""
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    source_id = result.get("source", "result")
    nodes.append({"id": source_id, "type": "source", "properties": {}})

    creator = result.get("creator")
    if creator:
        creator_id = str(creator)
        nodes.append(
            {"id": creator_id, "type": "person", "properties": {"role": "creator"}}
        )
        edges.append(
            {"source": creator_id, "target": source_id, "type": "CREATED", "properties": {}}
        )

    recipient = result.get("recipient")
    if recipient:
        recipient_id = str(recipient)
        nodes.append(
            {"id": recipient_id, "type": "person", "properties": {"role": "recipient"}}
        )
        edges.append(
            {"source": source_id, "target": recipient_id, "type": "ASSIGNED", "properties": {}}
        )

    return {"nodes": nodes, "edges": edges}


__all__ = ["store_result"]
