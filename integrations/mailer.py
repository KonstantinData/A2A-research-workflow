# integrations/mailer.py
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
import os


def send_email(to, subject, body):
    """
    Send an email via SMTP using credentials from environment variables.
    """

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", 587))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    secure = os.getenv("SMTP_SECURE", "starttls").lower()
    mail_from = os.getenv("MAIL_FROM", user)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr(("Internal Research Agent", mail_from))
    msg["To"] = to

    if secure == "ssl":
        smtp = smtplib.SMTP_SSL(host, port)
    else:
        smtp = smtplib.SMTP(host, port)
        if secure == "starttls":
            smtp.starttls()

    smtp.login(user, password)
    smtp.sendmail(mail_from, [to], msg.as_string())
    smtp.quit()
