import sys
import ssl
import json
import smtplib
import argparse
from email.message import EmailMessage
from datetime import datetime, timezone

DEFAULT_TEST_RECIPIENT = "info@condata.io"

# Load .env (searches upward from CWD)
try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore

    load_dotenv(find_dotenv(usecwd=True))
except Exception:
    pass

from config.settings import Settings


def build_message(sender: str, recipient: str) -> EmailMessage:
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    subject = f"A2A SMTP connectivity test - {ts}"
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content("Plain-text: This is an SMTP connectivity test from A2A.")
    msg.add_alternative(
        "<p>HTML: This is an <b>SMTP connectivity test</b> from A2A.</p>",
        subtype="html",
    )
    return msg


def send_via_smtp(
    host: str,
    port: int,
    username: str | None,
    password: str | None,
    sender: str,
    recipient: str,
    secure_mode: str = "starttls",
) -> dict:
    info = {
        "ok": False,
        "host": host,
        "port": port,
        "secure": secure_mode,
        "sender": sender,
        "recipient": recipient,
    }
    context = ssl.create_default_context()
    msg = build_message(sender, recipient)
    mode = (secure_mode or "starttls").lower()

    try:
        if mode in {"ssl", "smtps"} or port == 465:
            with smtplib.SMTP_SSL(
                host, port or 465, context=context, timeout=30
            ) as smtp:
                if username and password:
                    smtp.login(username, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port or 587, timeout=30) as smtp:
                smtp.ehlo()
                if mode in {"starttls", "tls", "1", "true", "yes"}:
                    smtp.starttls(context=context)
                    smtp.ehlo()
                if username and password:
                    smtp.login(username, password)
                smtp.send_message(msg)
        info["ok"] = True
    except Exception as e:
        info["error"] = str(e)
    return info


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send a test email via SMTP using env from .env"
    )
    parser.add_argument(
        "-t",
        "--to",
        dest="to",
        help=f"Recipient email (defaults to TEST_EMAIL_TO or {DEFAULT_TEST_RECIPIENT})",
    )
    args = parser.parse_args()

    settings = Settings()
    host = settings.smtp_host or ""
    port = int(settings.smtp_port or 0)
    secure = settings.smtp_secure or "starttls"
    user = settings.smtp_user or ""
    pwd = settings.smtp_pass or ""
    sender = settings.mail_from or user or ""
    recipient = args.to or settings.test_email_to or DEFAULT_TEST_RECIPIENT

    # Derive port if not provided
    if port <= 0:
        port = 465 if (secure or "").lower() in {"ssl", "smtps"} else 587

    # Minimal validation
    if not host or not sender or not recipient:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "Missing SMTP_HOST, MAIL_FROM or recipient (use --to or TEST_EMAIL_TO; default is info@condata.io).",
                    "have": {
                        "SMTP_HOST": bool(host),
                        "MAIL_FROM": bool(sender),
                        "recipient": bool(recipient),
                    },
                }
            )
        )
        return 2

    result = send_via_smtp(host, port, user, pwd, sender, recipient, secure_mode=secure)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
