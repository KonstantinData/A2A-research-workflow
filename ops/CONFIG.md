# Configuration

Document environment variables and secrets required for the workflow.
See repository README for common variables.

> **Note:** <span style="color:red">v2-only</span> – legacy Google OAuth environment names (previous client ID/secret or JSON variants) will fail at startup.

## Secrets
- `HUBSPOT_ACCESS_TOKEN`
- `GOOGLE_CLIENT_ID_V2`
- `GOOGLE_CLIENT_SECRET_V2`
- `GOOGLE_REFRESH_TOKEN`
- Optional: `GOOGLE_TOKEN_URI` (Default: https://oauth2.googleapis.com/token)
- `SMTP_HOST` (optional)
- `SMTP_USER` (optional)
- `SMTP_PASS` (optional)

## Email
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASS`
- `SMTP_SECURE`
- `MAIL_FROM` (sender address)
- `SMTP_FROM` (deprecated; automatically mapped to `MAIL_FROM` with a warning)
- `ALLOWLIST_EMAIL_DOMAIN` (optional)

## IMAP (optional)
- `IMAP_HOST`
- `IMAP_PORT`
- `IMAP_USER`
- `IMAP_PASS`
- `IMAP_FOLDER` (default: `INBOX`)

## Trigger Words
- `TRIGGER_WORDS_FILE` (defaults to `config/trigger_words.txt`)
