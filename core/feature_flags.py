# core/feature_flags.py
"""Feature toggle flags."""

import os

USE_PUSH_TRIGGERS: bool = os.getenv("USE_PUSH_TRIGGERS", "0") == "1"
ENABLE_PRO_SOURCES: bool = os.getenv("ENABLE_PRO_SOURCES", "0") == "1"
ATTACH_PDF_TO_HUBSPOT: bool = os.getenv("ATTACH_PDF_TO_HUBSPOT", "1") == "1"
ENABLE_SUMMARY: bool = os.getenv("ENABLE_SUMMARY", "0") == "1"

__all__ = [
    "USE_PUSH_TRIGGERS",
    "ENABLE_PRO_SOURCES",
    "ATTACH_PDF_TO_HUBSPOT",
    "ENABLE_SUMMARY",
]
