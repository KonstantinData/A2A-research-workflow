"""Command line interface for querying orchestrator events."""

from __future__ import annotations

import argparse
import json
from typing import Any, Optional

from app.core.event_store import EventStore
from app.core.query import get_labels, get_status


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="a2a-run")
    parser.add_argument(
        "--status",
        dest="status",
        metavar="EVENT_ID",
        help="Show the status of the given event identifier.",
    )
    return parser


def _render_status(event_id: str) -> tuple[dict[str, Any], int]:
    event = EventStore.get(event_id)
    if event is None:
        return {"event_id": event_id, "error": "not_found"}, 1

    payload = {
        "event_id": event.event_id,
        "status": get_status(event_id).value,
        "created_at": event.created_at.isoformat(),
        "updated_at": event.updated_at.isoformat(),
        "correlation_id": event.correlation_id,
        "labels": get_labels(event_id),
    }
    return payload, 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.status:
        payload, code = _render_status(args.status)
        print(json.dumps(payload, ensure_ascii=False))
        return code

    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
