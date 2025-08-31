import logging
import os
import re
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
    """Return ``True`` if the Levenshtein distance between ``a`` and ``b`` is ≤ 1."""
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
    # handle insert/delete
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


def contains_trigger(
    text: str | dict, triggers: Optional[Iterable[str]] = None, *, fuzzy: bool = True
) -> bool:
    """Return ``True`` when any trigger word is contained in ``text``.

    ``text`` may be a raw string or a dictionary representing a calendar event.
    The function normalises relevant fields and performs a token based
    comparison.  Optionally a fuzzy check (Levenshtein distance ≤ 1) can be
    applied to catch common typos.
    """
    if not text:
        return False

    if isinstance(text, dict):
        fields = [
            text.get("summary", ""),
            text.get("description", ""),
            text.get("location", ""),
        ]
        for att in text.get("attendees", []) or []:
            if isinstance(att, dict):
                fields.append(att.get("email", ""))
        norm = " ".join(_normalize_text(f or "") for f in fields if f)
    else:
        norm = _normalize_text(text)

    tokens = re.findall(r"\b\w+\b", norm)
    for trig in triggers or load_trigger_words():
        trig_norm = _normalize_text(trig)
        pattern = rf"\b{re.escape(trig_norm)}\b"
        if re.search(pattern, norm):
            return True
        if fuzzy and " " not in trig_norm:
            for token in tokens:
                if _levenshtein_leq1(token, trig_norm):
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
