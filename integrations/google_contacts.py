"""Google Contacts integration."""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict, List, Callable

try:  # pragma: no cover
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except ImportError:  # pragma: no cover - optional dependency
    Credentials = None  # type: ignore
    build = None  # type: ignore

from core.trigger_words import contains_trigger
from core.translate import to_us_business_english


def fetch_contacts() -> List[Dict[str, Any]]:
    """Fetch contacts with trigger words in their notes."""
    if Credentials is None or build is None:
        return []

    creds_b64 = os.getenv("GOOGLE_CREDENTIALS_JSON_BASE64")
    if not creds_b64:
        return []

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
        if not contains_trigger(notes):
            continue
        translated = to_us_business_english(notes.strip())
        results.append(
            {
                "resourceName": person.get("resourceName"),
                "names": person.get("names", []),
                "emailAddresses": person.get("emailAddresses", []),
                "notes": translated,
            }
        )
    return results


def scheduled_poll(contact_fetcher: Callable[[], List[Dict[str, Any]]] | None = None) -> List[Dict[str, Any]]:
    """Return normalized triggers from contacts."""
    fetcher = contact_fetcher or fetch_contacts
    contacts = fetcher()
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
