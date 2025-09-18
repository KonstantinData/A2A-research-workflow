"""Email listener agent to process task completion replies.

This module parses raw email messages for key/value pairs. It extracts the
``task_id`` from either the e-mail headers or the body, updates the associated
record in the task database with the supplied information and marks the task as
``completed``. When the task originates from internal company research, a new
research run is triggered using the provided data.

The expected body format is simple ``key: value`` lines or a JSON object. For
example::

    task_id: 1234
    creator: alice@example.com
    recipient: bob@example.com
    summary: Information about the company

"""
from __future__ import annotations

from email import message_from_string
from typing import Dict, Any
from datetime import datetime, timezone
import json
import time
import re

from core import tasks as tasks_db
from integrations import email_reader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_body(msg) -> str:
    """Return the plain text body from an ``email.message.Message``.

    E‑mail messages can be multipart (for example containing both a text and an
    HTML version or file attachments).  Only the ``text/plain`` parts are
    relevant for the listener, so this helper walks the message tree and
    extracts the payload from each plain text part.  Attachments and HTML
    segments are ignored.  The resulting fragments are normalised to UTF‑8 and
    joined together with newlines.
    """
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                if isinstance(payload, bytes):
                    parts.append(payload.decode(charset, errors="replace"))
                else:
                    parts.append(str(payload))
        return "\n".join(parts)
    payload = msg.get_payload(decode=True)
    if isinstance(payload, bytes):
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return str(payload)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_email(raw_email: str) -> Dict[str, str]:
    """Parse ``raw_email`` into a dictionary of values.

    The parser understands two formats: a JSON object or ``key: value`` pairs
    separated by newlines. ``task_id`` may also be supplied via ``X-Task-ID``
    header.
    """
    msg = message_from_string(raw_email)
    data: Dict[str, str] = {}

    # Header based task id
    for header in ("X-Task-ID", "Task-ID", "task_id"):
        val = msg.get(header)
        if val:
            data["task_id"] = val.strip()
            break

    body = _get_body(msg)

    # Try JSON first
    try:
        parsed = json.loads(body)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        for k, v in parsed.items():
            data[str(k).lower()] = str(v)
        return data

    # Fallback to key: value pairs
    for line in body.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        if key:
            data[key] = value.strip()
    return data


def extract_task_id(subject: str, body: str) -> str:
    """Extract task identifier from ``subject`` or ``body``."""
    match = re.search(r"Task ID[:\s]*([\w-]+)", subject, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"Task ID[:\s]*([\w-]+)", body, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def parse_missing_fields_from_body(body: str) -> Dict[str, str]:
    """Parse key-value pairs from e-mail ``body``."""
    data: Dict[str, str] = {}
    for line in body.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip().lower()] = value.strip()
    return data


def update_task(task_id: str, provided_data: Dict[str, str]) -> Dict[str, Any] | None:
    """Update task record with ``provided_data`` and mark as completed."""
    if not task_id:
        return None
    now = datetime.now(timezone.utc).isoformat()
    with tasks_db._connect() as conn:
        conn.execute(
            "UPDATE tasks SET missing_fields = ?, status = ?, updated_at = ? WHERE id = ?",
            (json.dumps(provided_data), "completed", now, task_id),
        )
        conn.commit()
    return tasks_db.get_task(task_id)


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def process_email(raw_email: str) -> Dict[str, Any]:
    """Process an incoming e-mail.

    Returns a dictionary containing the updated ``task`` info, the parsed
    ``data`` from the email and an optional ``result`` if a new research run was
    triggered.
    """
    msg = message_from_string(raw_email)
    subject = msg.get("subject", "")
    body = _get_body(msg)

    if "Task ID" in body or "missing details" in subject.lower():
        task_id = extract_task_id(subject, body)
        provided_data = parse_missing_fields_from_body(body)
        task = update_task(task_id, provided_data)
        result = None
        if task and task.get("trigger") == "internal_company_research":
            from agents.internal_company import run as internal_company_run

            try:
                result = internal_company_run(provided_data)
            except Exception:
                result = None
        return {"task": task, "data": provided_data, "result": result}

    parsed = parse_email(raw_email)
    task_id = parsed.pop("task_id", None)
    if not task_id:
        return {"error": "task_id not found"}

    now = datetime.now(timezone.utc).isoformat()
    with tasks_db._connect() as conn:
        conn.execute(
            "UPDATE tasks SET missing_fields = ?, updated_at = ? WHERE id = ?",
            (json.dumps(parsed), now, task_id),
        )
        conn.commit()

    task = tasks_db.update_task_status(task_id, "completed")

    result = None
    if task and task.get("trigger") == "internal_company_research":
        from agents.internal_company import run as internal_company_run

        try:
            result = internal_company_run(parsed)
        except Exception:
            result = None

    return {"task": task, "data": parsed, "result": result}


def run(raw_email: str) -> Dict[str, Any]:
    """Alias for :func:`process_email` to follow agent conventions."""
    return process_email(raw_email)


def has_pending_events() -> bool:
    """Return ``True`` if any tasks are awaiting email replies."""
    return any(tasks_db.pending_tasks())


def poll_pending_replies(interval: int = 600) -> None:
    """Poll mailbox every ``interval`` seconds while pending events exist."""
    while has_pending_events():
        try:
            for rep in email_reader.fetch_replies():
                run(json.dumps(rep))
        except Exception:
            pass
        time.sleep(interval)


__all__ = [
    "parse_email",
    "process_email",
    "run",
    "has_pending_events",
    "poll_pending_replies",
]
