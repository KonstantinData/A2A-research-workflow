import os
import re
import unicodedata
import logging

# Optional: GPT fallback
try:
    import openai

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if OPENAI_API_KEY:
        openai.api_key = OPENAI_API_KEY
    else:
        openai = None
except ImportError:
    openai = None

logger = logging.getLogger(__name__)

TRIGGERS = [
    "research",
    "meeting preparation",
    "business customer",
    "recherche",
    "meeting-vorbereitung",
    "geschäftskunde",
    "besuchsvorbereitung",
    "briefing",
    "business client",
    "kundenrecherche",
    "customer research",
    "meetingvorbereitung",
    "terminvorbereitung",
    "unternehmensrecherche",
]


def load_trigger_words(path: str | None = None) -> list[str]:
    """
    Load trigger words from config/trigger_words.txt if available,
    otherwise return default TRIGGERS.
    """
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    return TRIGGERS


def normalize_text(text: str) -> str:
    """Normalize string for trigger matching (casefold, remove accents)."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    return text.casefold().strip()


def contains_trigger(text: str, triggers: list[str] | None = None) -> str | None:
    """Check if any trigger word/phrase is contained in text."""
    if not text:
        return None
    norm = normalize_text(text)
    for trig in triggers or TRIGGERS:
        if trig in norm:
            return trig
    return None


def extract_company(title: str, trigger: str) -> str:
    """
    Extract company name from an event title.
    1. Look for trigger, then take remainder of string.
    2. Strip prefixes like 'Firma', 'Company'.
    3. If nothing found, optionally call GPT if available.
    """
    if not title or not trigger:
        return "Unknown"

    norm_title = normalize_text(title)
    norm_trigger = normalize_text(trigger)

    idx = norm_title.find(norm_trigger)
    if idx == -1:
        return "Unknown"

    # Take remainder after trigger
    remainder = title[idx + len(trigger) :].lstrip(" :-–—").strip()

    # Remove common prefixes
    remainder = re.sub(r"^(firma|company)\s+", "", remainder, flags=re.IGNORECASE)

    if remainder:
        return remainder

    # GPT fallback
    if openai:
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

    return "Unknown"
