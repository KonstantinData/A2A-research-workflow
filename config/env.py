"""Environment variable helpers and compatibility shims."""

from __future__ import annotations

from config.settings import SETTINGS


def ensure_mail_from() -> str:
    """Return the configured sender address or raise an explicit error."""

    if SETTINGS.mail_from:
        return SETTINGS.mail_from

    if SETTINGS.smtp_user:
        return SETTINGS.smtp_user

    raise RuntimeError(
        "MAIL_FROM (alias SMTP_FROM) must be configured for outbound e-mail."
    )

