# integrations/google_calendar.py
import os
import openai
from datetime import datetime, timezone
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from core.trigger_words import extract_company  # nur noch hier zentral
import logging

logger = logging.getLogger(__name__)

openai.api_key = os.getenv("OPENAI_API_KEY")


def _dt(s):
    """Helper: Parse Google Calendar date or dateTime into datetime object."""
    if not s:
        return None
    if "dateTime" in s:
        return datetime.fromisoformat(s["dateTime"].replace("Z", "+00:00"))
    return datetime.fromisoformat(s["date"] + "T00:00:00+00:00")


def _utc_now():
    """Wrapper so Tests (monkeypatch) can override current UTC time."""
    return datetime.utcnow().replace(tzinfo=timezone.utc)


def extract_company_ai(title: str, trigger: str) -> str:
    """
    Hybrid extraction for company names:
    1. Run regex-based rule extraction.
    2. If result is 'Unknown', fallback to OpenAI GPT (if available).
    """
    company = extract_company(title, trigger)
    if company and company != "Unknown":
        return company

    # GPT fallback
    if not openai.api_key:
        return "Unknown"

    prompt = f"""
    Extract the company name from the following calendar event title.
    Ignore leading words like 'Firma', 'Company', 'Firma Dr.', 'Client'.
    Return only the clean company name as plain text (no quotes, no punctuation).
    If no company is found, return "Unknown".

    Title: "{title}"
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        result = response["choices"][0]["message"]["content"].strip()
        return result if result else "Unknown"
    except Exception as e:
        logger.warning(f"GPT fallback failed: {e}")
        return "Unknown"


def normalize_event(ev, detected_trigger=None, creator_email=None, creator_name=None):
    """Normalize a raw Google Calendar event into internal schema."""
    title = ev.get("summary") or "Untitled"
    start_dt = _dt(ev.get("start", {}))
    end_dt = _dt(ev.get("end", {}))

    company = extract_company_ai(title, detected_trigger or "")

    normalized = {
        "event_id": ev.get("id", "unknown"),
        "ical_uid": ev.get("iCalUID"),
        "title": title,
        "company": company,
        "start_iso": start_dt.isoformat() if start_dt else None,
        "end_iso": end_dt.isoformat() if end_dt else None,
        "timezone": ev.get("start", {}).get("timeZone") or ev.get("timeZone"),
        "creator": creator_email,
        "creator_name": creator_name,
    }
    return normalized


def fetch_events():
    """Fetch today's events from Google Calendar API."""
    creds = Credentials(
        None,
        refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
    )
    service = build("calendar", "v3", credentials=creds)

    now = _utc_now()
    time_min = (now.replace(hour=0, minute=0, second=0, microsecond=0)).isoformat()
    time_max = (now.replace(hour=23, minute=59, second=59, microsecond=0)).isoformat()

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])
    return events
