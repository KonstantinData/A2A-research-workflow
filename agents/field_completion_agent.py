"""Field completion agent using OpenAI with a regex parser fallback."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

try:  # pragma: no cover - optional dependency
    import openai  # type: ignore
except Exception:  # pragma: no cover - openai may not be installed
    openai = None  # type: ignore


def _collect_text(trig: Dict[str, Any]) -> str:
    """Gather relevant text from event or contact payload."""
    payload = trig.get("payload") or {}
    parts: List[str] = []
    for key in ("summary", "description", "notes"):
        val = payload.get(key)
        if val:
            parts.append(str(val))
    for contact in payload.get("contacts", []) or []:
        if isinstance(contact, dict):
            note = contact.get("notes")
            if note:
                parts.append(str(note))
    return "\n".join(parts)


COMPANY_REGEX = r"\b([A-Z][A-Za-z0-9&.\-]*(?:\s+[A-Z][A-Za-z0-9&.\-]*)*\s(?:GmbH|AG|KG|SE|Ltd|Inc|LLC))\b"
DOMAIN_REGEX = r"\b([a-z0-9\-]+\.[a-z]{2,})(/[^\s]*)?\b"


def run(trig: Dict[str, Any]) -> Dict[str, Any]:
    """Attempt to fill missing ``company_name`` and ``domain``.

    The agent first tries to use the OpenAI API. If that fails or yields no
    data, a lightweight regex-based parser is applied to the same text.
    """
    text = _collect_text(trig)
    if not text:
        return {}

    ai_data: Dict[str, Any] = {}
    if openai is not None and os.getenv("OPENAI_API_KEY"):
        prompt = (
            "Extract the company name and web domain from the following text. "
            "Respond with a JSON object containing keys 'company_name' and 'domain'."
        )
        try:  # pragma: no cover - network call
            resp = openai.ChatCompletion.create(
                model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
            )
            content = resp["choices"][0]["message"]["content"]
            data = json.loads(content)
            if isinstance(data, dict):
                if data.get("company_name"):
                    ai_data["company_name"] = data["company_name"]
                if data.get("domain"):
                    ai_data["domain"] = data["domain"]
        except Exception:
            ai_data = {}

    result = dict(ai_data)

    if not result.get("company_name"):
        match = re.search(COMPANY_REGEX, text)
        if match:
            result["company_name"] = match.group(1)
        else:
            match = re.search(r"\b([A-Z][A-Za-z0-9&.\-]*(?:\s+[A-Z][A-Za-z0-9&.\-]*)*)", text)
            if match:
                result["company_name"] = match.group(1)

    if not result.get("domain"):
        match = re.search(DOMAIN_REGEX, text, re.IGNORECASE)
        if match:
            result["domain"] = match.group(1).lower().rstrip("/")

    return result


__all__ = ["run"]
