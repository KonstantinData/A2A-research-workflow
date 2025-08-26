from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Sequence

from .mailer import send_email  # tatsächlicher SMTP/Provider-Client


def _fmt(dt_iso: Optional[str], tz_str: Optional[str]) -> tuple[str, str]:
    if not dt_iso:
        return "", ""
    tz = ZoneInfo(tz_str) if tz_str else ZoneInfo("UTC")
    dt = datetime.fromisoformat(dt_iso).astimezone(tz)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")


def send(
    *,
    to: str,
    subject: str,
    body: str,
    sender: Optional[str] = None,
    attachments: Optional[Sequence[str]] = None,
    task_id: Optional[str] = None,
) -> None:
    """
    Generische Send-Funktion, die Tests monkeypatchen.
    """
    send_email(
        to=to,
        subject=subject,
        body=body,
        sender=sender,
        attachments=attachments,
        task_id=task_id,
    )


def send_missing_info_reminder(trigger: dict) -> None:
    creator_email = trigger.get("creator")
    creator_name = trigger.get("creator_name")
    greeting = f"Hi {creator_name}," if creator_name else "Hi there,"

    title = trigger.get("title") or "Untitled Event"
    date_s, start_s = _fmt(trigger.get("start_iso"), trigger.get("timezone"))
    _, end_s = _fmt(trigger.get("end_iso"), trigger.get("timezone"))

    missing_required = trigger.get("missing_required", ["Company", "Web domain"])
    missing_optional = trigger.get("missing_optional", ["Email", "Phone"])

    subject = f'[Research Agent] Missing Information – Event "{title}"'
    if date_s and start_s and end_s:
        subject += f" on {date_s}, {start_s}–{end_s}"

    req_lines = "\n".join([f"{f}:" for f in missing_required])
    opt_lines = "\n".join([f"{f}:" for f in missing_optional])

    body = f"""{greeting}

this is just a quick reminder from your Internal Research Agent.

For your research request regarding "{title}" on {date_s}, {start_s}–{end_s}, I still need a bit more information:

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

    send_email(to=creator_email, subject=subject, body=body)
