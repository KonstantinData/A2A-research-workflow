import logging
import os
import re
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Iterable, List, Optional

from core.utils import normalize_text as _normalize_text

try:  # Optional OpenAI integration
    import openai as _openai  # type: ignore
    if not os.getenv("OPENAI_API_KEY"):
        # Without an API key the library would fail on first use; keep it None so
        # tests run in offline environments.
        _openai = None  # type: ignore
except Exception:  # pragma: no cover - openai not installed
    _openai = None  # type: ignore

openai = _openai

logger = logging.getLogger(__name__)

TRIGGERS: List[str] = [
    "research",
    "meeting preparation",
    "meeting vorbereitung",
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


def normalize_text(text: str) -> str:
    """Delegate to :func:`core.utils.normalize_text` for full normalisation."""
    if isinstance(text, dict):
        text = text.get("summary") or ""
    return _normalize_text(text)


@lru_cache(maxsize=1)
def load_trigger_words() -> List[str]:
    """Return trigger words from an optional file or the built-in defaults."""
    path = os.getenv("TRIGGER_WORDS_FILE")
    if path and os.path.exists(path):  # pragma: no cover - trivial file IO
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return [line.strip() for line in fh if line.strip()]
        except Exception as exc:  # pragma: no cover - logging only
            logger.warning("Failed to read trigger words file %s: %s", path, exc)
    return TRIGGERS



def _levenshtein_leq1(a: str, b: str) -> bool:
    """Return True if Levenshtein distance between ``a`` and ``b`` is ≤ 1."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diffs = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        if len(diffs) == 1:
            return True
        if len(diffs) == 2:
            i, j = diffs
            if j == i + 1 and a[i] == b[j] and a[j] == b[i]:
                return True  # single transposition
        return False
    if len(a) < len(b):
        short, long = a, b
    else:
        short, long = b, a
    i = j = 0
    mismatches = 0
    while i < len(short) and j < len(long):
        if short[i] != long[j]:
            mismatches += 1
            if mismatches > 1:
                return False
            j += 1
        else:
            i += 1
            j += 1
    return True


def _fuzzy_match(word: str, trigger: str) -> bool:
    """Return True if word and trigger are sufficiently similar (ratio ≥ 0.9)."""
    ratio = SequenceMatcher(None, word, trigger).ratio()
    return ratio >= 0.9


def _hybrid_match(word: str, trigger: str) -> bool:
    """Use strict Levenshtein ≤1 first, then SequenceMatcher ≥0.9 as fallback."""
    return _levenshtein_leq1(word, trigger) or _fuzzy_match(word, trigger)


def contains_trigger(
    text: str | dict, triggers: Optional[Iterable[str]] = None
) -> bool:
    """Return ``True`` when any trigger word is contained in ``text``.

    The function accepts either a raw string or a dictionary representing an
    event. When an event dictionary is provided the ``summary``, ``description``,
    ``location`` and ``attendees[].email`` fields are inspected. Both exact
    word-boundary matches and fuzzy matches (typos within ~1 edit) are
    supported.
    """
    if not text:
        return False

    if isinstance(text, dict):
        parts = [
            text.get("summary") or "",
            text.get("description") or "",
            text.get("location") or "",
        ]
        attendee_emails = [
            a.get("email", "")
            for a in text.get("attendees", [])
            if isinstance(a, dict)
        ]
        parts.extend(attendee_emails)
        norm = " ".join(normalize_text(p) for p in parts if p)
    else:
        norm = normalize_text(text)

    words = re.findall(r"\b\w+\b", norm)

    for trig in triggers or load_trigger_words():
        norm_trig = normalize_text(trig)
        if re.search(rf"\b{re.escape(norm_trig)}\b", norm):
            return True
        for w in words:
            if _hybrid_match(w, norm_trig):
                return True

    return False


def extract_company(title: str, trigger: str) -> str:
    """Extract the company name from an event ``title``.

    The implementation first applies a small rule based approach.  When no
    company can be determined and the optional ``openai`` dependency is
    available, a minimal GPT prompt is used as a fall-back.  The function always
    returns a string and never raises errors so tests can run without network
    access.
    """
    if not title or not trigger:
        return "Unknown"

    norm_title = normalize_text(title)
    norm_trigger = normalize_text(trigger)
    idx = norm_title.find(norm_trigger)
    if idx == -1:
        return "Unknown"

    remainder = title[idx + len(trigger) :].lstrip(" :-–—").strip()
    remainder = re.sub(r"^(firma|company|client)\s+", "", remainder, flags=re.IGNORECASE)
    if remainder:
        return remainder

    if openai is not None:  # pragma: no cover - requires network
        prompt = (
            "Extract the company name from the calendar event title below. "
            "Ignore words like 'Firma', 'Company', 'Client'. "
            'Return only the plain company name, no quotes. If none, return "Unknown".\n\n'
            f'Title: "{title}"'
        )
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            text = resp["choices"][0]["message"]["content"].strip()
            return text or "Unknown"
        except Exception:  # pragma: no cover - defensive
            return "Unknown"
    return "Unknown"


__all__ = [
    "normalize_text",
    "load_trigger_words",
    "contains_trigger",
    "extract_company",
]
