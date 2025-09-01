import re
from typing import Optional

def extract_company(text: str) -> Optional[str]:
    """Extract a company name using a simple heuristic.

    Looks for patterns like ``Firma <Name>`` or ``Company: <Name>``. This is a
    stub for later NER-based extraction.
    """
    match = re.search(r"(?:firma|company)[:\s]+([^\n]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

def extract_domain(text: str) -> Optional[str]:
    match = re.search(r"[a-zA-Z0-9.-]+\.[a-z]{2,}", text)
    return match.group(0) if match else None

def extract_phone(text: str) -> Optional[str]:
    match = re.search(r"\+?\d[\d\s\/-]{7,}", text)
    return match.group(0) if match else None
