"""Field completion agent using OpenAI to enrich missing data."""
from __future__ import annotations

import json
import os
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


def run(trig: Dict[str, Any]) -> Dict[str, Any]:
    """Attempt to fill missing ``company_name`` and ``domain`` using OpenAI."""
    text = _collect_text(trig)
    if not text or openai is None or not os.getenv("OPENAI_API_KEY"):
        return {}
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
        result: Dict[str, Any] = {}
        if isinstance(data, dict):
            if data.get("company_name"):
                result["company_name"] = data["company_name"]
            if data.get("domain"):
                result["domain"] = data["domain"]
        return result
    except Exception:
        return {}


__all__ = ["run"]
