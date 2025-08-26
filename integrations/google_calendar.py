import os
import openai
from datetime import datetime, timezone
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from core.trigger_words import extract_company
import integrations.email_sender as email_sender  # ✅ für Tests, die email_sender patchen

# OpenAI Konfiguration
openai.api_key = os.getenv("OPENAI_API_KEY")


# ✅ Tests erwarten diese Hilfsfunktion, die sie monkeypatchen können
def _utc_now() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


def _dt(s):
    """Parse datetime or date-only dicts from Google Calendar API event objects."""
    if not s:
        return None
    if "dateTime" in s:
        return datetime.fromisoformat(s["dateTime"].replace("Z", "+00:00"))
    return datetime.fromisoformat(s["date"] + "T00:00:00+00:00")


def extract_company_ai(title: str, trigger: str) -> str:
    """
    Hybrid extraction for company names:
    1. Run regex-based rule extraction.
    2. If result is 'Unknown', fallback to OpenAI GPT.
    """
    company = extract_company(title, trigger)
    if company and company != "Unknown":
        return company

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
    except Exception:
        return "Unknown"


def normalize_event(ev, detected_trigger=None, creator_email=None, creator_name=None):
    """Normalize raw Google Calendar API event into a flat dict for processing."""
    title = ev.get("summary") or "Untitled"
    start_dt = _dt(ev.get("start", {}))
    end_dt = _dt(ev.get("end", {}))

    company = extract_company_ai(title, detected_trigger or "")

    normalized = {
        "event_id": ev.get("id"),
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
    """Fetch today's events from Google Calendar using OAuth2 credentials."""
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
    return events_result.get("items", [])
