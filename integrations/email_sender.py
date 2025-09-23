"""Utility helpers for sending notification e-mails.

The real project contains a rather feature rich mailer.  For the unit tests we
only need a very small subset which can easily be monkeypatched.  The
``send_reminder`` helper formats subject and body text in a deterministic way so
the tests can assert against it.
"""

from __future__ import annotations

import inspect
from datetime import datetime
from email.utils import make_msgid
from typing import Mapping, Optional, Sequence
import time
from pathlib import Path
import re

from config.env import ensure_mail_from
from config.settings import SETTINGS, email_allowed
from .mailer import send_email as _send_email  # tatsächlicher SMTP/Provider-Client
from core.utils import log_step
from app.integrations import email_reader
from app.core.policy.retry import MAX_ATTEMPTS, backoff_seconds


def _validate_recipient(to: str) -> str | None:
    """Return a normalised, allowlisted recipient address or ``None``.

    The higher level helpers historically enforced the optional
    ``ALLOWLIST_EMAIL_DOMAIN`` guard before attempting delivery.  We keep that
    behaviour here so that orchestration code continues to short-circuit early
    (avoiding misleading "mail sent" log entries) while also providing the
    validated address to the low level mailer for defence in depth.
    """

    # Basic email format validation
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', to.strip()):
        log_step(
            "mailer",
            "email_skipped_invalid_format",
            {"to": to},
            severity="warning",
        )
        return None
    
    cleaned_to = to.strip()
    allow_env = (
        getattr(SETTINGS, "allowlist_email_domain", None)
        or SETTINGS.allowlist_email_domain
    ).strip()
    allowed_domain = allow_env.lstrip("@").lower()

    if not cleaned_to:
        log_step(
            "mailer",
            "email_skipped_invalid_domain",
            {"to": to, "allowed_domain": allowed_domain or allow_env or None},
            severity="warning",
        )
        return None

    if allowed_domain:
        if "@" not in cleaned_to:
            log_step(
                "mailer",
                "email_skipped_invalid_domain",
                {"to": cleaned_to, "allowed_domain": allowed_domain},
                severity="warning",
            )
            return None
        recipient_domain = cleaned_to.rsplit("@", 1)[-1].lower()
        # Allow sender's own domain for internal notifications
        sender_address = (
            getattr(SETTINGS, "mail_from", None)
            or getattr(SETTINGS, "smtp_user", None)
            or SETTINGS.mail_from
            or SETTINGS.smtp_user
            or ""
        )
        sender_domain = (
            sender_address.rsplit("@", 1)[-1].lower()
            if "@" in sender_address
            else ""
        )
        if recipient_domain != allowed_domain and recipient_domain != sender_domain:
            log_step(
                "mailer",
                "email_skipped_invalid_domain",
                {"to": cleaned_to, "allowed_domain": allowed_domain, "sender_domain": sender_domain},
                severity="warning",
            )
            return None

    return cleaned_to


def _assert_allowlisted(address: str) -> None:
    domain = address.rsplit("@", 1)[-1].strip().lower()
    assert email_allowed(address), f"Recipient domain '{domain}' is not allowlisted"


def _supports_keyword_argument(func, name: str) -> bool:
    """Return ``True`` if *func* accepts ``name`` as a keyword argument."""

    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        # Builtins or mocks without introspectable signatures – assume they
        # tolerate extra keywords so correlation details are not dropped.
        return True

    if name in signature.parameters:
        return True

    return any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )


def _generate_message_id(identifier: Optional[str]) -> str | None:
    if not identifier:
        return None
    token = re.sub(r"[^A-Za-z0-9.-]", "", identifier)
    if not token:
        return None
    return make_msgid(idstring=f"task-{token}")


def _record_outbound_correlation(
    message_id: Optional[str], *, task_id: Optional[str], event_id: Optional[str]
) -> None:
    if not message_id:
        return
    try:
        email_reader.record_outbound_message(
            message_id, task_id=task_id, event_id=event_id
        )
    except Exception as exc:
        # Correlation is best-effort and must not interfere with sending.
        log_step(
            "mailer",
            "correlation_record_failed",
            {
                "message_id": message_id,
                "task_id": task_id,
                "event_id": event_id,
                "error": str(exc),
            },
            severity="warning",
        )


def _deliver(
    to: str,
    subject: str,
    body: str,
    attachments: Optional[Sequence[str]] = None,
    *,
    message_id: Optional[str] = None,
    headers: Optional[Mapping[str, str]] = None,
) -> None:
    """Send message using environment configured SMTP credentials."""
    host = SETTINGS.smtp_host or ""
    port = int(SETTINGS.smtp_port or 587)
    user = SETTINGS.smtp_user or ""
    password = SETTINGS.smtp_pass or ""
    ensure_mail_from()
    mail_from = (
        SETTINGS.mail_from
        or user
    )
    secure = str(
        SETTINGS.smtp_secure
        or "ssl"
    ).lower()
    if not host or not user or not password:
        if SETTINGS.live_mode == 1:
            raise RuntimeError("SMTP not configured; cannot send emails in LIVE mode")
        return
    allow_env = (
        getattr(SETTINGS, "allowlist_email_domain", None)
        or SETTINGS.allowlist_email_domain
    ).strip()
    allowed_domain = allow_env.lstrip("@").lower() or None

    validated_to = to.strip()
    _assert_allowlisted(validated_to)

    _send_email(
        host,
        port,
        user,
        password,
        mail_from,
        validated_to,
        subject,
        body,
        secure=secure,
        attachments=list(attachments or []),
        allowed_domain=allowed_domain,
        message_id=message_id,
        headers=headers,
    )


def send(
    *,
    to: str,
    subject: str,
    body: str,
    sender: Optional[str] = None,
    attachments: Optional[Sequence[str]] = None,
    task_id: Optional[str] = None,
    event_id: Optional[str] = None,
    headers: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """
    Generische Send-Funktion, die Tests monkeypatchen.
    """
    _assert_allowlisted(to)

    validated_to = _validate_recipient(to)
    if not validated_to:
        return

    message_id = _generate_message_id(event_id or task_id)

    deliver_kwargs = {}
    if message_id and _supports_keyword_argument(_deliver, "message_id"):
        deliver_kwargs["message_id"] = message_id
    if headers and _supports_keyword_argument(_deliver, "headers"):
        deliver_kwargs["headers"] = headers

    try:
        _deliver(validated_to, subject, body, attachments, **deliver_kwargs)
        log_step("orchestrator", "mail_sent", {"to": validated_to, "subject": subject})
        _record_outbound_correlation(message_id, task_id=task_id, event_id=event_id)
    except Exception as e:  # pragma: no cover - network errors
        log_step(
            "orchestrator",
            "mail_error",
            {
                "to": validated_to,
                "subject": subject,
                "error": str(e),
                "task_id": task_id,
            },
            severity="critical",
        )
        raise
    return message_id


def send_email(
    to: str,
    subject: str,
    body: str,
    *,
    sender: Optional[str] = None,
    attachments: Optional[Sequence[str]] = None,
    task_id: Optional[str] = None,
    event_id: Optional[str] = None,
    headers: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """Wrapper around the low level mailer with logging and retries.

    ``task_id`` or ``event_id`` may be supplied for correlation so that
    replies can be matched to pending workflow items.  When provided a
    deterministic ``Message-ID`` is generated and persisted for the IMAP reply
    processor."""

    _assert_allowlisted(to)

    validated_to = _validate_recipient(to)
    if not validated_to:
        return

    attach_paths: list[str] = []
    body_extra = ""
    for path in attachments or []:
        p = Path(path)
        size = p.stat().st_size if p.exists() else 0
        if size <= 5 * 1024 * 1024:
            attach_paths.append(str(p))
        else:
            body_extra += f"\nDownload report: {p}"
            log_step(
                "mailer",
                "attachment_skipped_too_large",
                {"path": str(p), "size": size},
                severity="warning",
            )
    if body_extra:
        body = f"{body}\n\n{body_extra.strip()}"

    last_exc: Exception | None = None
    message_id = _generate_message_id(event_id or task_id)
    deliver_kwargs = {}
    if message_id and _supports_keyword_argument(_deliver, "message_id"):
        deliver_kwargs["message_id"] = message_id
    if headers and _supports_keyword_argument(_deliver, "headers"):
        deliver_kwargs["headers"] = headers

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            _deliver(
                validated_to,
                subject,
                body,
                attach_paths,
                **deliver_kwargs,
            )
            log_step(
                "orchestrator",
                "mail_sent",
                {"to": validated_to, "subject": subject},
            )
            _record_outbound_correlation(message_id, task_id=task_id, event_id=event_id)
            return
        except Exception as e:  # pragma: no cover - network errors
            last_exc = e
            if attempt >= MAX_ATTEMPTS:
                log_step(
                    "orchestrator",
                    "report_not_sent",
                    {
                        "to": validated_to,
                        "subject": subject,
                        "error": str(e),
                        "task_id": task_id,
                        "attempt": attempt,
                    },
                    severity="critical",
                )
                break
            delay = backoff_seconds(attempt)
            log_step(
                "mailer",
                "send_retry",
                {
                    "to": validated_to,
                    "subject": subject,
                    "attempt": attempt,
                    "backoff_seconds": round(delay, 2),
                },
                severity="warning",
            )
            time.sleep(delay)
    if last_exc:
        raise last_exc
    return message_id


def request_missing_fields(
    task: dict, missing_fields: list[str], recipient_email: str
) -> None:
    """
    Send a collegial email to the event/contact creator asking for missing details.
    The colleague can simply reply to this email with the information.
    Updating the calendar entry is optional.
    """
    if not recipient_email:
        return

    subject = "Could you provide a few missing details for our research request?"

    body = (
        f"Hello,\n\n"
        f"We are working on your request (Task ID: {task.get('id')}). "
        f"Some details are still missing:\n"
        + "".join(f"- {field}\n" for field in missing_fields)
        + (
            "\nIt would be very helpful if you could simply reply to this email with the missing details. "
            "If you prefer, you may also update the calendar entry, but that’s optional.\n\n"
            "Thanks a lot for your support!\n\n"
            "Best regards,\n"
            "Your colleague from the Research Team"
        )
    )

    send_kwargs = {}
    task_id = task.get("id")
    if task_id and _supports_keyword_argument(send_email, "task_id"):
        send_kwargs["task_id"] = task_id

    send_email(
        to=recipient_email,
        subject=subject,
        body=body,
        **send_kwargs,
    )


def send_missing_fields_reminder(
    task: dict, missing_fields: list[str], recipient_email: str, final: bool = False
) -> None:
    """Send a friendly reminder if missing fields are still not provided."""
    if not recipient_email or not missing_fields:
        return

    subject = (
        f"Final reminder: details needed to complete your request (Task ID: {task.get('id')})"
        if final
        else f"Quick check-in on the missing details (Task ID: {task.get('id')})"
    )

    missing_fmt = "".join(f"- {f}\n" for f in missing_fields)
    body = (
        "Hello,\n\n"
        f"{'This is a friendly final reminder' if final else 'Just a quick check-in'} regarding your request "
        f"(Task ID: {task.get('id')}).\n"
        "We’re still missing the following details:\n"
        f"{missing_fmt}\n"
        "You can simply reply to this email with the information.\n"
        "Updating the calendar entry is optional.\n\n"
        "Thanks a lot for your help!\n"
        "\n"
        "Best regards,\n"
        "Your colleague from the Research Team"
    )

    validated_to = _validate_recipient(recipient_email)
    if not validated_to:
        return
    send_kwargs = {}
    task_id = task.get("id")
    if task_id and _supports_keyword_argument(send_email, "task_id"):
        send_kwargs["task_id"] = task_id

    send_email(
        to=validated_to,
        subject=subject,
        body=body,
        **send_kwargs,
    )


def send_reminder(
    *,
    to: str,
    creator_email: str,
    creator_name: Optional[str],
    event_id: Optional[str],
    event_title: str,
    event_start: Optional[datetime],
    event_end: Optional[datetime],
    missing_fields: Sequence[str],
    task_id: Optional[str] = None,
) -> None:
    """Send a reminder requesting missing information.

    In addition to the existing parameters, an optional ``task_id`` may be
    provided.  When present the task identifier is included in the subject
    line so that replies can be correlated to pending tasks.  The message
    content remains friendly and lists required and optional fields.
    """

    start_s = event_start.strftime("%Y-%m-%d, %H:%M") if event_start else ""
    end_s = event_end.strftime("%H:%M") if event_end else ""

    # Build subject: include event title and optionally the task identifier
    subject = f'[Research Agent] Missing Information – "{event_title}"'
    if start_s and end_s:
        subject += f" on {start_s.split(',')[0]}, {start_s.split(', ')[1]}–{end_s}"
    if task_id:
        subject += f" – Task {task_id}"

    req_lines = "\n".join(f"{f}:" for f in missing_fields)
    opt_lines = "\n".join(f"{f}:" for f in ["Email", "Phone"])

    greeting = f"Hi {creator_name}," if creator_name else f"Hi {creator_email},"

    body = f"""{greeting}

this is just a quick reminder from your Internal Research Agent.

For your research request regarding "{event_title}" on {start_s or 'unknown'}, {start_s.split(', ')[1] if start_s else ''}–{end_s}, I still need a bit more information:

I definitely need the following details (required):
{req_lines}

If you also have these details, please include them (optional):
{opt_lines}

Please reply to this email directly with the missing information.
You might also update the calendar entry or contact record with these details.

Once I receive the information, the process will automatically continue — no further action needed from you.

Thanks a lot for your support!

"Your Internal Research Agent"
"""

    # Allow reminders only for a configured company domain (optional)
    allow = SETTINGS.allowlist_email_domain
    if allow and not to.lower().endswith(f"@{allow.lower()}"):
        log_step(
            "mailer",
            "reminder_skipped_invalid_domain",
            {"to": to},
            severity="warning",
        )
        return
    send(
        to=to,
        subject=subject,
        body=body,
        task_id=task_id or event_id,
        event_id=event_id,
    )


# Backwards compatibility helper used in a few places in the project.
def send_missing_info_reminder(
    trigger: dict,
) -> None:  # pragma: no cover - thin wrapper
    creator_email = trigger.get("creator")
    creator_name = trigger.get("creator_name")
    title = trigger.get("title") or "Untitled Event"
    start_iso = trigger.get("start_iso")
    end_iso = trigger.get("end_iso")
    # timezone not used in current implementation
    start_dt = datetime.fromisoformat(start_iso) if start_iso else None
    end_dt = datetime.fromisoformat(end_iso) if end_iso else None
    send_reminder(
        to=creator_email,
        creator_email=creator_email,
        creator_name=creator_name,
        event_id=trigger.get("event_id"),
        event_title=title,
        event_start=start_dt,
        event_end=end_dt,
        missing_fields=trigger.get("missing_required", ["Company", "Web domain"]),
    )
