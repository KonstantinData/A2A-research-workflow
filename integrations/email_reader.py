"""IMAP email reader for replies to the Internal Research agent."""
from __future__ import annotations

import email
import imaplib
import json
import os
import re
import time
from email.header import decode_header
from email.message import Message
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import parser
from core.utils import log_step
from config.settings import SETTINGS
from app.core.policy.retry import MAX_ATTEMPTS, backoff_seconds


def _state_path() -> Path:
    return SETTINGS.workflows_dir / "email_reader_state.json"


def _normalize_message_id(value: str | None) -> str:
    if not value:
        return ""
    cleaned = value.strip()
    if cleaned.startswith("<"):
        cleaned = cleaned[1:]
    if cleaned.endswith(">"):
        cleaned = cleaned[:-1]
    return cleaned.strip().lower()


def _load_state() -> Dict[str, Any]:
    default = {"processed_message_ids": [], "correlation_index": {}}
    path = _state_path()
    if not path.exists():
        return default.copy()
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return default.copy()

    processed = data.get("processed_message_ids")
    if not isinstance(processed, list):
        processed = []

    raw_index = data.get("correlation_index")
    index: Dict[str, Dict[str, str]] = {}
    if isinstance(raw_index, dict):
        for key, value in raw_index.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                continue
            normalized_key = _normalize_message_id(key)
            if not normalized_key:
                continue
            entry = {}
            task_val = value.get("task_id")
            event_val = value.get("event_id")
            if isinstance(task_val, str) and task_val:
                entry["task_id"] = task_val
            if isinstance(event_val, str) and event_val:
                entry["event_id"] = event_val
            if entry:
                index[normalized_key] = entry

    return {"processed_message_ids": processed, "correlation_index": index}


def _save_state(state: Dict[str, Any]) -> None:
    path = _state_path()
    payload = {
        "processed_message_ids": sorted(
            {
                _normalize_message_id(mid)
                for mid in state.get("processed_message_ids", [])
                if _normalize_message_id(mid)
            }
        ),
        "correlation_index": state.get("correlation_index", {}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def record_outbound_message(
    message_id: str,
    *,
    task_id: str | None = None,
    event_id: str | None = None,
) -> None:
    """Persist correlation metadata for an outbound message.

    The IMAP reply processor records outbound message identifiers so that
    incoming replies can be matched purely via headers.  The mapping is stored
    alongside the processed message tracking state to ensure restarts do not
    lose correlation information.
    """

    normalized = _normalize_message_id(message_id)
    if not normalized:
        return

    state = _load_state()
    index = state.setdefault("correlation_index", {})
    entry = index.get(normalized, {}).copy()
    if task_id:
        entry["task_id"] = task_id
    if event_id:
        entry["event_id"] = event_id
    if entry:
        index[normalized] = entry
        state["correlation_index"] = index
        _save_state(state)


def _decode(value: str) -> str:
    parts = decode_header(value)
    decoded = ""
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded += part.decode(charset or "utf-8", errors="ignore")
        else:
            decoded += part
    return decoded


_MESSAGE_ID_PATTERN = re.compile(r"<[^>]+>")
_TASK_ID_PATTERN = re.compile(r"Task ([A-Fa-f0-9-]{36})")
_EVENT_ID_PATTERN = re.compile(r"Event (\d{4}-\d{2}-\d{2})_(\d{4})")


def _header_message_ids(msg: Message) -> List[str]:
    message_ids: List[str] = []
    for header in ("In-Reply-To", "References"):
        for value in msg.get_all(header, []):
            if not value:
                continue
            matches = _MESSAGE_ID_PATTERN.findall(value)
            if matches:
                message_ids.extend(_normalize_message_id(m) for m in matches)
            else:
                message_ids.append(_normalize_message_id(value))
    return [mid for mid in message_ids if mid]


def _correlate_from_headers(msg: Message, index: Dict[str, Dict[str, str]]) -> Tuple[str, str]:
    for message_id in _header_message_ids(msg):
        entry = index.get(message_id)
        if not entry:
            continue
        task_id = entry.get("task_id", "")
        event_id = entry.get("event_id", "")
        if task_id or event_id:
            return task_id, event_id
    return "", ""


def _extract_ids_from_subject(subject: str) -> Tuple[str, str]:
    task_id = ""
    event_id = ""
    task_match = _TASK_ID_PATTERN.search(subject)
    if task_match:
        task_id = task_match.group(1)
    event_match = _EVENT_ID_PATTERN.search(subject)
    if event_match:
        event_id = f"{event_match.group(1)}_{event_match.group(2)}"
    return task_id, event_id


def _update_correlation_index(
    index: Dict[str, Dict[str, str]],
    message_ids: List[str],
    task_id: str,
    event_id: str,
) -> bool:
    changed = False
    if not message_ids or not (task_id or event_id):
        return False
    for mid in message_ids:
        if not mid:
            continue
        entry = index.get(mid, {})
        if task_id and entry.get("task_id") != task_id:
            entry = entry.copy() if entry else {}
            entry["task_id"] = task_id
            index[mid] = entry
            changed = True
        if event_id and entry.get("event_id") != event_id:
            entry = entry.copy() if entry else {}
            entry["event_id"] = event_id
            index[mid] = entry
            changed = True
    return changed


def fetch_replies() -> List[Dict[str, Any]]:
    """Fetch unread replies and extract fields."""
    host = os.getenv("IMAP_HOST")
    port = int(os.getenv("IMAP_PORT", "993"))
    user = os.getenv("IMAP_USER")
    pwd = os.getenv("IMAP_PASS")
    folder = os.getenv("IMAP_FOLDER", "INBOX")
    if not all([host, user, pwd]):
        log_step(
            "email_reader",
            "imap_not_configured",
            {
                "host_configured": bool(host),
                "user_configured": bool(user),
                "folder": folder,
            },
            severity="info",
        )
        return []

    state = _load_state()
    processed_ids = {
        mid
        for mid in (
            _normalize_message_id(m) for m in state.get("processed_message_ids", [])
        )
        if mid
    }
    correlation_index: Dict[str, Dict[str, str]] = state.get("correlation_index", {}).copy()
    state_changed = False

    results: List[Dict[str, Any]] = []
    imap = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            imap = imaplib.IMAP4_SSL(host, port)
            imap.login(user, pwd)
            imap.select(folder)
            break
        except (imaplib.IMAP4.error, OSError) as exc:
            if imap is not None:
                try:
                    imap.logout()
                except Exception:
                    pass
                imap = None
            if attempt >= MAX_ATTEMPTS:
                log_step(
                    "email_reader",
                    "imap_connect_failed",
                    {"host": host, "folder": folder, "error": str(exc)},
                    severity="error",
                )
                return []
            delay = backoff_seconds(attempt)
            log_step(
                "email_reader",
                "imap_retry",
                {
                    "host": host,
                    "folder": folder,
                    "attempt": attempt,
                    "backoff_seconds": round(delay, 2),
                },
                severity="warning",
            )
            time.sleep(delay)
    if imap is None:
        return []
    typ, data = imap.search(None, "UNSEEN")
    ids = data[0].split() if typ == "OK" else []
    for msg_id in ids:
        typ, msg_data = imap.fetch(msg_id, "(RFC822)")
        if typ != "OK" or not msg_data:
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        message_id_header = msg.get("Message-ID") or msg.get("Message-Id")
        message_id = _normalize_message_id(message_id_header)
        if not message_id:
            try:
                uid = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
            except Exception:
                uid = str(msg_id)
            message_id = f"imap-{uid}"

        if message_id in processed_ids:
            log_step(
                "email_reader",
                "reply_duplicate_skipped",
                {"message_id": message_id},
                severity="info",
            )
            imap.store(msg_id, "+FLAGS", "(\\Seen)")
            continue

        subject = _decode(msg.get("Subject", ""))
        if "[Research Agent] Missing Information" not in subject:
            continue

        header_task_id, header_event_id = _correlate_from_headers(msg, correlation_index)
        task_id = header_task_id
        event_id = header_event_id

        subject_task_id, subject_event_id = _extract_ids_from_subject(subject)
        if not task_id and subject_task_id:
            task_id = subject_task_id
        if not event_id and subject_event_id:
            event_id = subject_event_id

        referenced_ids = _header_message_ids(msg)
        if _update_correlation_index(
            correlation_index, referenced_ids, task_id, event_id
        ):
            state_changed = True

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

        processed_ids.add(message_id)
        if _update_correlation_index(
            correlation_index, [message_id], task_id, event_id
        ):
            state_changed = True
        state_changed = True

        if fields:
            results.append(
                {
                    "creator": from_addr,
                    "task_id": task_id or event_id,
                    "event_id": event_id,
                    "fields": fields,
                }
            )
            log_step(
                "email_reader",
                "reply_received",
                {
                    "event_id": event_id,
                    "task_id": task_id or event_id,
                    "fields_completed": list(fields.keys()),
                    "message_id": message_id,
                    "from": from_addr,
                },
            )
        else:
            log_step(
                "email_reader",
                "reply_no_fields",
                {
                    "task_id": task_id or event_id,
                    "event_id": event_id,
                    "message_id": message_id,
                },
                severity="info",
            )

        if not (task_id or event_id):
            log_step(
                "email_reader",
                "reply_unmatched",
                {"message_id": message_id},
                severity="warning",
            )

        imap.store(msg_id, "+FLAGS", "(\\Seen)")

    if state_changed:
        _save_state(
            {
                "processed_message_ids": list(processed_ids),
                "correlation_index": correlation_index,
            }
        )

    imap.logout()
    return results


def poll_replies(interval: int = 600, shutdown_flag=None) -> None:
    """Continuously poll the inbox for replies every ``interval`` seconds."""
    while True:
        if shutdown_flag and shutdown_flag.is_set():
            break
        try:
            fetch_replies()
        except Exception as e:
            log_step(
                "email_reader",
                "poll_error",
                {"error": str(e)},
                severity="warning",
            )
        time.sleep(interval)


__all__ = ["fetch_replies", "poll_replies", "record_outbound_message"]

