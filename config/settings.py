"""Centralised runtime configuration for the autonomous workflow."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

_logger = logging.getLogger(__name__)


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        _logger.warning("Invalid integer for %s=%r; using default %d", name, raw, default)
        return default


def _list_env(name: str, default: str) -> List[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _default_root() -> Path:
    project_root = os.environ.get("PROJECT_ROOT")
    if project_root:
        return Path(project_root).expanduser()
    return Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    env: str = field(default_factory=lambda: os.environ.get("ENV", "dev"))
    service_version: str = field(
        default_factory=lambda: os.environ.get("SERVICE_VERSION", "0.0.0")
    )

    root_dir: Path = field(default_factory=_default_root)
    logs_dir: Path = field(init=False)
    workflows_dir: Path = field(init=False)
    output_dir: Path = field(init=False)
    exports_dir: Path = field(init=False)
    artifacts_dir: Path = field(init=False)

    cal_lookback_days: int = field(default_factory=lambda: _int_env("CAL_LOOKBACK_DAYS", 1))
    cal_lookahead_days: int = field(
        default_factory=lambda: _int_env("CAL_LOOKAHEAD_DAYS", 14)
    )
    google_calendar_ids: List[str] = field(
        default_factory=lambda: _list_env("GOOGLE_CALENDAR_IDS", "primary")
    )

    admin_email: str = field(default_factory=lambda: os.environ.get("ADMIN_EMAIL", ""))
    live_mode: int = field(default_factory=lambda: _int_env("LIVE_MODE", 1))
    require_hubspot: int = field(
        default_factory=lambda: _int_env("REQUIRE_HUBSPOT", 0)
    )
    test_mode: bool = field(default_factory=lambda: _bool_env("A2A_TEST_MODE", False))

    smtp_host: str = field(default_factory=lambda: os.environ.get("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: _int_env("SMTP_PORT", 587))
    smtp_user: str = field(default_factory=lambda: os.environ.get("SMTP_USER", ""))
    smtp_pass: str = field(default_factory=lambda: os.environ.get("SMTP_PASS", ""))
    smtp_secure: str = field(default_factory=lambda: os.environ.get("SMTP_SECURE", "ssl"))
    mail_from: str = field(init=False)
    allowlist_email_domain: str = field(
        default_factory=lambda: os.environ.get("ALLOWLIST_EMAIL_DOMAIN", "")
    )
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

    imap_host: str = field(default_factory=lambda: os.environ.get("IMAP_HOST", ""))
    imap_port: int = field(default_factory=lambda: _int_env("IMAP_PORT", 993))
    imap_user: str = field(default_factory=lambda: os.environ.get("IMAP_USER", ""))
    imap_pass: str = field(default_factory=lambda: os.environ.get("IMAP_PASS", ""))
    imap_secure: str = field(default_factory=lambda: os.environ.get("IMAP_SECURE", "ssl"))
    imap_folder: str = field(default_factory=lambda: os.environ.get("IMAP_FOLDER", "INBOX"))
    imap_search: str = field(default_factory=lambda: os.environ.get("IMAP_SEARCH", "UNSEEN"))
    imap_use_uid: bool = field(default_factory=lambda: _bool_env("IMAP_USE_UID", True))
    imap_since_days: int = field(
        default_factory=lambda: _int_env("IMAP_SINCE_DAYS", 7)
    )
    imap_test_limit: Optional[int] = field(
        default_factory=lambda: int(os.environ.get("IMAP_TEST_LIMIT", "0") or 0)
    )

    event_db_url: Optional[str] = field(
        default_factory=lambda: os.environ.get("EVENT_DB_URL")
    )
    event_db_path: Optional[Path] = field(
        default_factory=lambda: _optional_path("EVENT_DB_PATH")
    )
    tasks_db_url: Optional[str] = field(
        default_factory=lambda: os.environ.get("TASKS_DB_URL")
    )
    tasks_db_path: Optional[Path] = field(
        default_factory=lambda: _optional_path("TASKS_DB_PATH")
    )

    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo"))
    hubspot_access_token: str = field(
        default_factory=lambda: os.environ.get("HUBSPOT_ACCESS_TOKEN", "")
    )
    google_client_id: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLIENT_ID", "")
    )
    google_client_secret: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLIENT_SECRET", "")
    )
    google_refresh_token: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_REFRESH_TOKEN", "")
    )
    google_token_uri: str = field(
        default_factory=lambda: os.environ.get(
            "GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"
        )
    )

    internal_fetch_redis_url: str = field(
        default_factory=lambda: os.environ.get("INTERNAL_FETCH_REDIS_URL", "")
    )
    internal_fetch_cache_ttl: int = field(
        default_factory=lambda: _int_env("INTERNAL_FETCH_CACHE_TTL", 3600)
    )

    test_email_to: str = field(default_factory=lambda: os.environ.get("TEST_EMAIL_TO", ""))
    run_live_google_tests: bool = field(
        default_factory=lambda: _bool_env("RUN_LIVE_GOOGLE_TESTS", False)
    )

    trigger_words_path: Optional[Path] = field(
        default_factory=lambda: _optional_path("TRIGGER_WORDS_FILE")
    )
    trigger_words_override: str = field(
        default_factory=lambda: os.environ.get("TRIGGER_WORDS", "")
    )
    trigger_regex: str = field(default_factory=lambda: os.environ.get("TRIGGER_REGEX", ""))

    run_id: str = field(default_factory=lambda: os.environ.get("RUN_ID", ""))
    stage: str = field(default_factory=lambda: os.environ.get("STAGE", ""))

    github_repository: str = field(
        default_factory=lambda: os.environ.get("GITHUB_REPOSITORY", "")
    )
    github_token: str = field(default_factory=lambda: os.environ.get("GITHUB_TOKEN", ""))

    def __post_init__(self) -> None:
        self.root_dir = self._resolve_root(self.root_dir)
        self.logs_dir = self._resolve_path(os.environ.get("LOGS_DIR", "logs"))
        self.output_dir = self._resolve_path(os.environ.get("OUTPUT_DIR", "output"))
        self.artifacts_dir = self._resolve_path(
            os.environ.get("ARTIFACTS_DIR", "artifacts")
        )

        workflows_override = os.environ.get("WORKFLOWS_DIR")
        if workflows_override:
            self.workflows_dir = self._resolve_path(workflows_override)
        else:
            subdir = os.environ.get("WORKFLOWS_SUBDIR", "workflows")
            self.workflows_dir = self.logs_dir / subdir

        exports_override = os.environ.get("EXPORTS_DIR")
        if exports_override:
            self.exports_dir = self._resolve_path(exports_override)
        else:
            subdir = os.environ.get("EXPORTS_SUBDIR", "exports")
            self.exports_dir = self.output_dir / subdir

        mail_from = os.environ.get("MAIL_FROM")
        if mail_from and mail_from.strip():
            self.mail_from = mail_from.strip()
        else:
            smtp_from = os.environ.get("SMTP_FROM")
            self.mail_from = smtp_from.strip() if smtp_from else ""

        if self.test_mode:
            self.cal_lookback_days = 1
            self.cal_lookahead_days = 14
            self.live_mode = 0

        if self.event_db_path is not None:
            self.event_db_path = self._resolve_path(self.event_db_path)
        if self.tasks_db_path is not None:
            self.tasks_db_path = self._resolve_path(self.tasks_db_path)

    def _resolve_root(self, value: Path) -> Path:
        value = value.expanduser()
        if not value.is_absolute():
            value = (Path(__file__).resolve().parent.parent / value).resolve()
        return value

    def _resolve_path(self, value: str | Path) -> Path:
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = (self.root_dir / candidate).resolve()
        return candidate

    @property
    def smtp_allowlist_domain(self) -> str:
        return self.allowlist_email_domain


def _optional_path(name: str) -> Optional[Path]:
    raw = os.environ.get(name)
    if not raw:
        return None
    try:
        return Path(raw).expanduser()
    except (TypeError, ValueError):
        _logger.warning("Invalid path in %s: %r", name, raw)
        return None


SETTINGS = Settings()

__all__ = ["SETTINGS", "Settings"]
