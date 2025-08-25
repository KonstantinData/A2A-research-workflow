import unicodedata

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
