import unicodedata
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

def normalize_text(text: str) -> str:
    if not text:
        return ""
    # Unicode normalisieren (Gedankenstrich etc. angleichen)
    text = unicodedata.normalize("NFKC", text)
    # Alles klein
    text = text.lower()
    # Alle Varianten von Bindestrichen vereinheitlichen
    dash_variants = ["–", "—", "‐", "‑", "-", "‒", "―"]  # includes U+2011 (non-breaking hyphen)
    for d in dash_variants:
        text = text.replace(d, "-")
    # Umlaute vereinheitlichen (optional für bessere Treffer)
    text = (
        text.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
    )
    return text


@lru_cache()
def _required_fields() -> Dict[str, List[str]]:
    path = Path(__file__).resolve().parents[1] / "config" / "required_fields.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def required_fields(context: str) -> List[str]:
    return _required_fields().get(context, [])
