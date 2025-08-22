"""Google Contacts integration."""

from __future__ import annotations
import os
from typing import Any, Dict, List

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except ImportError:
    Credentials = None  # type: ignore
    build = None  # type: ignore

from core.trigger_words import load_trigger_words  # ✅


def fetch_contacts() -> List[Dict[str, Any]]:
    """Fetch contacts from Google People API."""
    # ✅ Early-exit: keine Trigger -> keine API, keine Credentials nötig
    words = load_trigger_words()
    if not words:
        return []

    if Credentials is None or build is None:
        raise ImportError("google-api-python-client is required")

    client_id = os.getenv("GOOGLE_CLIENT_ID_V2")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET_V2")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise RuntimeError("Google OAuth credentials not configured")

    creds_info = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
    }

    creds = Credentials.from_authorized_user_info(creds_info)

    service = build("people", "v1", credentials=creds)
    results = (
        service.people()
        .connections()
        .list(
            resourceName="people/me",
            pageSize=2000,
            personFields="names,emailAddresses",
        )
        .execute()
    )

    connections = results.get("connections", [])
    contacts: List[Dict[str, Any]] = []
    for person in connections:
        names = person.get("names", [])
        emails = person.get("emailAddresses", [])
        if names and emails:
            contacts.append(
                {
                    "name": names[0].get("displayName"),
                    "email": emails[0].get("value"),
                }
            )
    return contacts


def scheduled_poll() -> List[Dict[str, Any]]:
    """Scheduled poll that returns normalized contact payloads."""
    contacts = fetch_contacts()
    normalized: List[Dict[str, Any]] = []
    for contact in contacts:
        # Test-kompatibel (Mocks liefern emailAddresses)
        email = contact.get("email")
        if not email and "emailAddresses" in contact:
            email_entries = contact.get("emailAddresses", [])
            if email_entries and isinstance(email_entries, list):
                email = email_entries[0].get("value")

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
