"""Translation utilities for ensuring U.S. Business English output."""

from __future__ import annotations

import os
from typing import Optional

try:  # pragma: no cover - optional dependency
    import openai
except Exception:  # pragma: no cover - openai may not be installed
    openai = None  # type: ignore


def to_us_business_english(text: str) -> str:
    """Translate ``text`` to U.S. Business English.

    Uses OpenAI's ChatCompletion API when available and configured via
    ``OPENAI_API_KEY`` and ``OPENAI_MODEL`` environment variables. If the API is
    not available, the original text is returned unchanged.
    """
    if not text:
        return text

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    if openai and api_key:
        openai.api_key = api_key
        try:  # pragma: no cover - network call
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Translate to U.S. Business English."},
                    {"role": "user", "content": text},
                ],
            )
            content: Optional[str] = response.choices[0].message.get("content")
            if content:
                return content.strip()
        except Exception:
            return text
    return text

__all__ = ["to_us_business_english"]
