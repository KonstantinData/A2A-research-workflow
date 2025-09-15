from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class _Settings:
    """Centralised runtime configuration loaded from environment variables."""

    # --- Calendar / Contacts ---
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

    # --- LIVE / Policy ---
    # Email-Empfänger für Operator-/Admin-Alarme (Pflicht im LIVE)
    admin_email: str = field(default_factory=lambda: os.getenv("ADMIN_EMAIL", ""))
    # Harte LIVE-Schaltung (1=LIVE, 0=DEV); steuert Fail-Fast & No-Dummy-Policy
    live_mode: int = field(default_factory=lambda: int(os.getenv("LIVE_MODE", "1")))
    # Erzwingt HubSpot-Live-Daten (1) statt statischer Dummydaten (0)
    require_hubspot: int = field(
        default_factory=lambda: int(os.getenv("REQUIRE_HUBSPOT", "0"))
    )
    # Erlaubt statische Unternehmensdaten (nur für DEV; im LIVE=0)
    allow_static_company_data: int = field(
        default_factory=lambda: int(os.getenv("ALLOW_STATIC_COMPANY_DATA", "0"))
    )
    # Optional: E-Mail-Allowlist-Domain zum Schutz vor Fehlversand
    smtp_allowlist_domain: str = field(
        default_factory=lambda: os.getenv("ALLOWLIST_EMAIL_DOMAIN", "")
    )


SETTINGS = _Settings()
