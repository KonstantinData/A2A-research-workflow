"""Utilities for loading and matching trigger words."""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from typing import Iterable


DEFAULT_TRIGGER_PATH = Path("config/trigger_words.txt")


def _read_trigger_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    words: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            word = line.strip()
            if word:
                words.append(word.lower())
    return words


@lru_cache(maxsize=1)
def load_trigger_words() -> set[str]:
    """Load trigger words from file specified by ``TRIGGER_WORDS_FILE`` env variable."""
    path = Path(os.getenv("TRIGGER_WORDS_FILE", DEFAULT_TRIGGER_PATH))
    return set(_read_trigger_file(path))


def contains_trigger(text: str | None, words: Iterable[str] | None = None) -> bool:
    """Return True if ``text`` contains any trigger word.

    Comparison is case-insensitive and ignores leading/trailing whitespace.
    ``words`` can be supplied to override the loaded set (primarily for testing).
    """
    if not text:
        return False
    normalized = text.strip().lower()
    trigger_words = set(w.lower() for w in words) if words else load_trigger_words()
    return any(tw in normalized for tw in trigger_words)
