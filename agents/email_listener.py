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
from datetime import datetime
import json

from core import tasks as tasks_db

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


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def process_email(raw_email: str) -> Dict[str, Any]:
    """Process an incoming e-mail.

    Returns a dictionary containing the updated ``task`` info, the parsed
    ``data`` from the email and an optional ``result`` if a new research run was
    triggered.
    """
    parsed = parse_email(raw_email)
    task_id = parsed.pop("task_id", None)
    if not task_id:
        return {"error": "task_id not found"}

    now = datetime.utcnow().isoformat()
    # Update task record with provided data
    with tasks_db._connect() as conn:
        conn.execute(
            "UPDATE tasks SET missing_fields = ?, updated_at = ? WHERE id = ?",
            (json.dumps(parsed), now, task_id),
        )
        conn.commit()

    task = tasks_db.update_task_status(task_id, "completed")

    result = None
    if task and task.get("trigger") == "internal_company_research":
        # Lazy import to avoid heavy dependencies unless necessary
        from agents.internal_company import run as internal_company_run

        try:
            result = internal_company_run(parsed)
        except Exception:
            # If renewed research fails we still return the task info
            result = None

    return {"task": task, "data": parsed, "result": result}


def run(raw_email: str) -> Dict[str, Any]:
    """Alias for :func:`process_email` to follow agent conventions."""
    return process_email(raw_email)


__all__ = ["parse_email", "process_email", "run"]
