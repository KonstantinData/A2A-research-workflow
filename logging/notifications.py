"""Notification logging utilities."""

from __future__ import annotations

from typing import Optional
from datetime import datetime
import logging
import json

logger = logging.getLogger("notifications")
if not logger.handlers:
    handler = logging.FileHandler("notification.log")
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

def log_email(
    sender: str,
    recipient: str,
    subject: str,
    task_id: Optional[str] = None,
    *,
    timestamp: Optional[str] = None,
) -> None:
    """Log an e-mail notification event."""
    ts = timestamp or datetime.utcnow().isoformat()
    payload = {
        "timestamp": ts,
        "sender": sender,
        "recipient": recipient,
        "subject": subject,
        "task_id": task_id,
    }
    logger.info(json.dumps(payload))

__all__ = ["log_email"]
