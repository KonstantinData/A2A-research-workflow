"""Environment variable helpers and compatibility shims."""

from __future__ import annotations

import logging
import os

_logger = logging.getLogger(__name__)
_warned_smtp_from = False


def ensure_mail_from() -> None:
    """Ensure ``MAIL_FROM`` is populated, falling back to ``SMTP_FROM`` if needed."""
    global _warned_smtp_from

    mail_from = os.getenv("MAIL_FROM")
    if mail_from and mail_from.strip():
        return

    smtp_from = os.getenv("SMTP_FROM")
    if smtp_from and smtp_from.strip():
        os.environ["MAIL_FROM"] = smtp_from
        if not _warned_smtp_from:
            _logger.warning(
                "Environment variable SMTP_FROM is deprecated; please use MAIL_FROM instead."
            )
            _warned_smtp_from = True

