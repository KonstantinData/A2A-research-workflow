from __future__ import annotations

from typing import Dict, List


def build_reminder_email(source: str, recipient: str, missing: List[str]) -> Dict[str, str]:
    """Build reminder e-mail in English and German for missing information."""
    missing_list = ", ".join(missing)
    subject = f"Information missing for new {source} entry"

    body_en = (
        "Hello,\n\n"
        f"Some required information is missing in your new {source} entry.\n\n"
        f"Missing fields: {missing_list}\n\n"
        "Please update the entry and provide the missing details.\n\n"
        "Thank you."
    )

    body_de = (
        "Hallo,\n\n"
        f"bei deinem neuen {source}-Eintrag fehlen wichtige Pflichtangaben.\n\n"
        f"Fehlende Felder: {missing_list}\n\n"
        "Bitte ergänze die fehlenden Informationen.\n\n"
        "Vielen Dank."
    )

    return {
        "recipient": recipient,
        "subject": subject,
        "body": body_en + "\n\n---\n\n" + body_de,
    }
