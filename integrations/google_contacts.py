"""Google Contacts integration."""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict, List

try:  # pragma: no cover
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except ImportError:  # pragma: no cover - optional dependency
    Credentials = None  # type: ignore
    build = None  # type: ignore

from core.trigger_words import contains_trigger, load_trigger_words


def fetch_contacts() -> List[Dict[str, Any]]:
    """Fetch contacts with trigger words in their notes."""
    words = load_trigger_words()
    if not words:
        return []

    if Credentials is None or build is None:
        raise ImportError("google-api-python-client is required")

    creds_b64 = os.getenv("GOOGLE_CREDENTIALS_JSON_BASE64")
    if not creds_b64:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON_BASE64 not set")

    creds_info = json.loads(base64.b64decode(creds_b64).decode("utf-8"))
    creds = Credentials.from_authorized_user_info(creds_info)

    service = build("people", "v1", credentials=creds)
    connections = (
        service.people()
        .connections()
        .list(
            resourceName="people/me",
            personFields="names,emailAddresses,biographies",
        )
        .execute()
        .get("connections", [])
    )

    results: List[Dict[str, Any]] = []
    for person in connections:
        biographies = person.get("biographies", [])
        notes = biographies[0].get("value", "") if biographies else ""
        if contains_trigger(notes, words):
            results.append(
                {
                    "resourceName": person.get("resourceName"),
                    "names": person.get("names", []),
                    "emailAddresses": person.get("emailAddresses", []),
                    "notes": notes.strip(),
                }
            )
    return results


def scheduled_poll() -> List[Dict[str, Any]]:
    """Scheduled poll that returns normalized trigger payloads."""
    contacts = fetch_contacts()
    normalized: List[Dict[str, Any]] = []
    for contact in contacts:
        emails = contact.get("emailAddresses", [])
        email = emails[0].get("value") if emails else None
        if not email:
            continue
        normalized.append(
            {
                "creator": email,
                "trigger_source": "contacts",
                "recipient": email,
                "payload": contact,
            }
        )
    return normalized
