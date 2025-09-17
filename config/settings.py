from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .env import ensure_mail_from


ensure_mail_from()
_log = logging.getLogger(__name__)


def _default_root() -> Path:
    project_root = os.getenv("PROJECT_ROOT")
    if project_root:
        return Path(project_root).expanduser()
    return Path(__file__).resolve().parent.parent


def _int_env(name: str, default: int) -> int:
    """Parse integer env var with trimming + safe fallback + warning."""
    raw = os.getenv(name, str(default))
    try:
        return int(str(raw).strip())
    except Exception:
        _log.warning("Invalid int for %s=%r; falling back to %d", name, raw, default)
        return int(default)


def _bool_env(name: str, default: bool) -> bool:
    """Parse boolean-ish env var (1/0, true/false, yes/no, on/off)."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class _Settings:
    """Centralised runtime configuration loaded from environment variables."""

    root_dir: Path = field(default_factory=_default_root)
    logs_dir: Path = field(init=False)
    workflows_dir: Path = field(init=False)
    output_dir: Path = field(init=False)
    exports_dir: Path = field(init=False)
    artifacts_dir: Path = field(init=False)

    # --- Calendar / Contacts ---
    cal_lookback_days: int = field(
        default_factory=lambda: _int_env("CAL_LOOKBACK_DAYS", 1)
    )
    cal_lookahead_days: int = field(
        default_factory=lambda: _int_env("CAL_LOOKAHEAD_DAYS", 14)
    )
    google_calendar_ids: List[str] = field(
        default_factory=lambda: [
            c.strip()
            for c in os.getenv("GOOGLE_CALENDAR_IDS", "primary").split(",")
            if c.strip()
        ]
    )
    contacts_page_size: int = field(
        default_factory=lambda: _int_env("CONTACTS_PAGE_SIZE", 200)
    )
    contacts_page_limit: int = field(
        default_factory=lambda: _int_env("CONTACTS_PAGE_LIMIT", 10)
    )

    # --- LIVE / Policy ---
    # Email-Empfänger für Operator-/Admin-Alarme (Pflicht im LIVE)
    admin_email: str = field(default_factory=lambda: os.getenv("ADMIN_EMAIL", ""))
    # Harte LIVE-Schaltung (1=LIVE, 0=DEV); steuert Fail-Fast & No-Dummy-Policy
    live_mode: int = field(default_factory=lambda: _int_env("LIVE_MODE", 1))
    # Explizites Test-Profil (macht Tests deterministisch)
    test_mode: bool = field(default_factory=lambda: _bool_env("A2A_TEST_MODE", False))
    # Erzwingt HubSpot-Live-Daten (1) statt statischer Dummydaten (0)
    require_hubspot: int = field(default_factory=lambda: _int_env("REQUIRE_HUBSPOT", 0))
    # Optional: E-Mail-Allowlist-Domain zum Schutz vor Fehlversand
    smtp_allowlist_domain: str = field(
        default_factory=lambda: os.getenv("ALLOWLIST_EMAIL_DOMAIN", "")
    )

    # --- Feature Flags ---
    use_push_triggers: bool = field(
        default_factory=lambda: _bool_env("USE_PUSH_TRIGGERS", False)
    )
    enable_pro_sources: bool = field(
        default_factory=lambda: _bool_env("ENABLE_PRO_SOURCES", False)
    )
    attach_pdf_to_hubspot: bool = field(
        default_factory=lambda: _bool_env("ATTACH_PDF_TO_HUBSPOT", True)
    )
    enable_summary: bool = field(
        default_factory=lambda: _bool_env("ENABLE_SUMMARY", False)
    )
    enable_graph_storage: bool = field(
        default_factory=lambda: _bool_env("ENABLE_GRAPH_STORAGE", False)
    )
    allow_static_company_data: bool = field(
        default_factory=lambda: _bool_env("ALLOW_STATIC_COMPANY_DATA", False)
    )

    def __post_init__(self) -> None:
        self.root_dir = Path(self.root_dir).expanduser()
        if not self.root_dir.is_absolute():
            base = Path(__file__).resolve().parent.parent
            self.root_dir = (base / self.root_dir).resolve()
        else:
            self.root_dir = self.root_dir.resolve()

        self.logs_dir = self._resolve_path(os.getenv("LOGS_DIR", "logs"))
        self.output_dir = self._resolve_path(os.getenv("OUTPUT_DIR", "output"))
        self.artifacts_dir = self._resolve_path(os.getenv("ARTIFACTS_DIR", "artifacts"))

        workflows_override = os.getenv("WORKFLOWS_DIR")
        if workflows_override:
            self.workflows_dir = self._resolve_path(workflows_override)
        else:
            workflows_subdir = os.getenv("WORKFLOWS_SUBDIR", "workflows")
            self.workflows_dir = self._resolve_subpath(self.logs_dir, workflows_subdir)

        exports_override = os.getenv("EXPORTS_DIR")
        if exports_override:
            self.exports_dir = self._resolve_path(exports_override)
        else:
            exports_subdir = os.getenv("EXPORTS_SUBDIR", "exports")
            self.exports_dir = self._resolve_subpath(self.output_dir, exports_subdir)

        # TEST-PROFIL: harte Defaults + LIVE off, unabhängig von CI-ENV
        if self.test_mode:
            if os.getenv("CAL_LOOKBACK_DAYS"):
                _log.warning("Ignoring CAL_LOOKBACK_DAYS in TEST mode")
            if os.getenv("CAL_LOOKAHEAD_DAYS"):
                _log.warning("Ignoring CAL_LOOKAHEAD_DAYS in TEST mode")
            self.cal_lookback_days = 1
            self.cal_lookahead_days = 14
            self.live_mode = 0  # niemals hart failen (z. B. SMTP) in Tests

    def _resolve_path(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.root_dir / path
        return path

    @staticmethod
    def _resolve_subpath(base: Path, value: str | Path) -> Path:
        sub_path = Path(value).expanduser()
        if sub_path.is_absolute():
            return sub_path
        return base / sub_path


SETTINGS = _Settings()
