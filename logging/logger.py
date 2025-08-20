"""Structured JSON logging utilities."""

from __future__ import annotations

import json
import logging
import sys


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - trivial
        payload = {
            "run_id": getattr(record, "run_id", ""),
            "stage": getattr(record, "stage", ""),
            "level": record.levelname.lower(),
            "message": record.getMessage(),
        }
        return json.dumps(payload)


def get_logger(*, run_id: str, stage: str) -> logging.Logger:
    """Return a logger emitting JSON payloads."""

    base = logging.getLogger(f"a2a.{run_id}.{stage}")
    base.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    base.addHandler(handler)
    base.setLevel(logging.INFO)
    base.propagate = False

    return logging.LoggerAdapter(base, {"run_id": run_id, "stage": stage})


__all__ = ["get_logger"]
