from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class _Settings:
    """Centralised runtime configuration loaded from environment variables."""

    cal_lookback_days: int = field(
        default_factory=lambda: int(os.getenv("CAL_LOOKBACK_DAYS", "1"))
    )
    cal_lookahead_days: int = field(
        default_factory=lambda: int(os.getenv("CAL_LOOKAHEAD_DAYS", "14"))
    )
    google_calendar_ids: List[str] = field(
        default_factory=lambda: [
            c.strip()
            for c in os.getenv("GOOGLE_CALENDAR_IDS", "primary").split(",")
            if c.strip()
        ]
    )
    contacts_page_size: int = field(
        default_factory=lambda: int(os.getenv("CONTACTS_PAGE_SIZE", "200"))
    )
    contacts_page_limit: int = field(
        default_factory=lambda: int(os.getenv("CONTACTS_PAGE_LIMIT", "10"))
    )


SETTINGS = _Settings()
