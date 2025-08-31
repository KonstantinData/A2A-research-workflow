"""IMAP email reader for replies to the Internal Research agent."""
from __future__ import annotations

import email
import imaplib
import os
import re
import time
import logging
from email.header import decode_header
from pathlib import Path
from typing import Any, Dict, List
import importlib.util as _ilu

from core import parser

_JSONL_PATH = Path(__file__).resolve().parents[1] / "logging" / "jsonl_sink.py"
_spec = _ilu.spec_from_file_location("jsonl_sink", _JSONL_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
append_jsonl = _mod.append

_REPLY_LOG = Path("logs") / "workflows" / "replies.jsonl"

logger = logging.getLogger(__name__)


def _decode(value: str) -> str:
    parts = decode_header(value)
    decoded = ""
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded += part.decode(charset or "utf-8", errors="ignore")
        else:
            decoded += part
    return decoded


def fetch_replies() -> List[Dict[str, Any]]:
    """Fetch unread replies and extract fields."""
    host = os.getenv("IMAP_HOST")
    port = int(os.getenv("IMAP_PORT", "993"))
    user = os.getenv("IMAP_USER")
    pwd = os.getenv("IMAP_PASS")
    folder = os.getenv("IMAP_FOLDER", "INBOX")
    if not all([host, user, pwd]):
        logger.info("IMAP credentials not configured; skipping fetch")
        append_jsonl(
            _REPLY_LOG,
            {"status": "imap_not_configured", "severity": "info"},
        )
        return []

    results: List[Dict[str, Any]] = []
    imap = imaplib.IMAP4_SSL(host, port)
    imap.login(user, pwd)
    imap.select(folder)
    typ, data = imap.search(None, "UNSEEN")
    ids = data[0].split() if typ == "OK" else []
    for msg_id in ids:
        typ, msg_data = imap.fetch(msg_id, "(RFC822)")
        if typ != "OK":
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        subject = _decode(msg.get("Subject", ""))
        if "[Research Agent] Missing Information" not in subject:
            continue
        # Extract a task identifier when present (e.g. "Task 123e4567-e89b-12d3-a456-426655440000")
        task_match = re.search(r"Task ([A-Fa-f0-9-]{36})", subject)
        # Fallback: extract event ID pattern from older subjects
        event_match = re.search(r"Event (\d{4}-\d{2}-\d{2})_(\d{4})", subject)
        task_id = ""
        event_id = ""
        if task_match:
            task_id = task_match.group(1)
        if event_match:
            event_id = f"{event_match.group(1)}_{event_match.group(2)}"
        from_addr = email.utils.parseaddr(msg.get("From"))[1]

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                    try:
                        body = part.get_payload(decode=True).decode(
                            part.get_content_charset() or "utf-8", errors="ignore"
                        )
                    except Exception:
                        body = ""
                    break
        else:
            try:
                body = msg.get_payload(decode=True).decode(
                    msg.get_content_charset() or "utf-8", errors="ignore"
                )
            except Exception:
                body = ""

        fields: Dict[str, Any] = {}
        company = parser.extract_company(body)
        if company:
            fields["company"] = company
        domain = parser.extract_domain(body)
        if domain:
            fields["domain"] = domain
        phone = parser.extract_phone(body)
        if phone:
            fields["phone"] = phone
        mail_match = re.search(r"[\w.%-]+@[\w.-]+", body)
        if mail_match:
            fields["email"] = mail_match.group(0)

        if fields:
            results.append(
                {
                    "creator": from_addr,
                    "task_id": task_id or event_id,
                    "event_id": event_id,
                    "fields": fields,
                }
            )
            append_jsonl(
                _REPLY_LOG,
                {
                    "status": "reply_received",
                    "event_id": event_id,
                    "task_id": task_id or event_id,
                    "fields_completed": list(fields.keys()),
                    "source": "email",
                },
            )
        imap.store(msg_id, "+FLAGS", "(\\Seen)")

    imap.logout()
    return results


def poll_replies(interval: int = 600) -> None:
    """Continuously poll the inbox for replies every ``interval`` seconds."""
    while True:
        try:
            fetch_replies()
        except Exception as e:
            append_jsonl(
                _REPLY_LOG,
                {"status": "error", "error": str(e), "severity": "warning"},
            )
        time.sleep(interval)


__all__ = ["fetch_replies", "poll_replies"]

