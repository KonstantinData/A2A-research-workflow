"""Structured JSON logging utilities.

This module exposes :func:`get_logger` which returns a standard library logger
configured to emit JSON objects to stdout.  Each log record includes the
``run_id`` and ``stage`` of the current workflow along with the log level and
message.  The function is intentionally lightweight and has no external
dependencies beyond the Python standard library.
"""

from __future__ import annotations

from typing import Optional, Dict, Any
import json
import uuid
import os
import sys

# Import the standard library logging module under a different name to avoid
# confusing it with this package.
import logging as _py_logging


class JSONFormatter(_py_logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: _py_logging.LogRecord) -> str:  # type: ignore[override]
        payload: Dict[str, Any] = {
            "run_id": getattr(record, "run_id", None),
            "stage": getattr(record, "stage", None),
            "level": record.levelname.lower(),
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        # Drop keys with ``None`` values to keep the output compact.
        return json.dumps({k: v for k, v in payload.items() if v is not None})


def get_logger(
    run_id: Optional[str] = None,
    stage: Optional[str] = None,
    level: int = _py_logging.INFO,
) -> _py_logging.Logger:
    """Return a logger that emits JSON log records.

    Parameters
    ----------
    run_id:
        Identifier for the current workflow run.  If omitted, an attempt is made
        to read ``RUN_ID`` from the environment or a random UUID is used.
    stage:
        Stage of the workflow emitting the logs.  If ``None`` the value of the
        ``STAGE`` environment variable (if any) is used.
    level:
        Logging level to apply to the returned logger.
    """

    logger = _py_logging.getLogger("a2a")

    if logger.handlers:
        # Logger was already configured; still update contextual information.
        # Any existing ``ContextFilter`` will update these values on subsequent
        # records.
        for flt in logger.filters:
            if isinstance(flt, _ContextFilter):
                flt.run_id = run_id or flt.run_id
                flt.stage = stage or flt.stage
        return logger

    run_id = run_id or os.getenv("RUN_ID") or str(uuid.uuid4())
    stage = stage or os.getenv("STAGE")

    handler = _py_logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JSONFormatter())

    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False

    context_filter = _ContextFilter(run_id=run_id, stage=stage)
    logger.addFilter(context_filter)
    return logger


class _ContextFilter(_py_logging.Filter):
    """Attach ``run_id`` and ``stage`` to log records."""

    def __init__(self, run_id: Optional[str], stage: Optional[str]) -> None:
        super().__init__()
        self.run_id = run_id
        self.stage = stage

    def filter(self, record: _py_logging.LogRecord) -> bool:  # type: ignore[override]
        record.run_id = self.run_id
        record.stage = self.stage
        return True


__all__ = ["get_logger"]

