import unicodedata

def normalize_text(text: str) -> str:
    if not text:
        return ""
    # Unicode normalisieren (Gedankenstrich etc. angleichen)
    text = unicodedata.normalize("NFKC", text)
    # Alles klein
    text = text.lower()
    # Alle Varianten von Bindestrichen vereinheitlichen
    text = text.replace("–", "-").replace("—", "-").replace("‐", "-")
    # Umlaute vereinheitlichen (optional für bessere Treffer)
    text = (
        text.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
    )
    return text
