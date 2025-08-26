import os
import openai
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from .trigger_words import extract_company

# OpenAI Key
openai.api_key = os.getenv("OPENAI_API_KEY")


def _dt(s):
    """Parse RFC3339 datetime or all-day date into datetime."""
    if not s:
        return None
    if "dateTime" in s:
        return datetime.fromisoformat(s["dateTime"].replace("Z", "+00:00"))
    return datetime.fromisoformat(s["date"] + "T00:00:00+00:00")


def extract_company_ai(title: str, trigger: str) -> str:
    """
    Hybrid extraction for company names:
    1. Regex-based extraction
    2. Fallback: OpenAI GPT
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


def normalize_event(ev, detected_trigger, creator_email, creator_name):
    title = ev.get("summary") or "Untitled"
    start_dt = _dt(ev.get("start", {}))
    end_dt = _dt(ev.get("end", {}))

    company = extract_company_ai(title, detected_trigger)

    return {
        "event_id": ev["id"],
        "ical_uid": ev.get("iCalUID"),
        "title": title,
        "company": company,
        "start_iso": start_dt.isoformat() if start_dt else None,
        "end_iso": end_dt.isoformat() if end_dt else None,
        "timezone": ev.get("start", {}).get("timeZone") or ev.get("timeZone"),
        "creator": creator_email,
        "creator_name": creator_name,
    }
