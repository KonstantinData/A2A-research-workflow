from datetime import datetime
from zoneinfo import ZoneInfo
from .mailer import send_email as _send_email  # interne Referenz


def _fmt(dt_iso, tz_str):
    if not dt_iso:
        return "", ""
    tz = ZoneInfo(tz_str) if tz_str else ZoneInfo("UTC")
    dt = datetime.fromisoformat(dt_iso).astimezone(tz)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")


def send_missing_info_reminder(trigger):
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

    body = f"""{greeting}

this is just a quick reminder from your Internal Research Agent.

For your research request regarding "{title}" on {date_s}, {start_s}–{end_s}, I still need a bit more information:

I definitely need the following details (required):
{chr(10).join([f"{f}:" for f in missing_required])}

If you also have these details, please include them (optional):
{chr(10).join([f"{f}:" for f in missing_optional])}

Please reply to this email directly with the missing information.
You might also update the calendar entry or contact record with these details.

Once I receive the information, the process will automatically continue — no further action needed from you.

Thanks a lot for your support!

"Your Internal Research Agent"
"""

    _send_email(to=creator_email, subject=subject, body=body)


# ---------------------------------------------------------------------------
# ✅ Kompatibilitäts-Aliase für Tests
# ---------------------------------------------------------------------------


def send(*, to, subject, body, **kwargs):
    """Alias für Tests (wird in mehreren Testdateien direkt gepatcht)."""
    return _send_email(to=to, subject=subject, body=body, **kwargs)


# expose auch den importierten Namen so, dass Tests `email_sender.send_email` patchen können
send_email = _send_email
