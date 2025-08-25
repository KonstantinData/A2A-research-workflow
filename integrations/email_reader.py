"""IMAP email reader for replies to the Internal Research agent."""
from __future__ import annotations

import email
import imaplib
import os
import re
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

_LOG_PATH = Path("logs") / "workflows" / "email_reader.jsonl"


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
        raise RuntimeError("IMAP credentials not configured")

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
        if not (
            subject.startswith("[Agent: Internal Research]")
            or subject.startswith("Missing Information for Your Research Request")
        ):
            continue
        from_addr = email.utils.parseaddr(msg.get("From"))[1]
        task_id = msg.get("In-Reply-To") or msg.get("References") or ""

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
            results.append({"creator": from_addr, "task_id": task_id, "fields": fields})
            append_jsonl(
                _LOG_PATH,
                {"status": "read", "from": from_addr, "task_id": task_id},
            )
        imap.store(msg_id, "+FLAGS", "(\\Seen)")

    imap.logout()
    return results


__all__ = ["fetch_replies"]

