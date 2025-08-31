# Configuration

Document environment variables and secrets required for the workflow.
See repository README for common variables.

## Secrets
- `HUBSPOT_ACCESS_TOKEN`
- Erforderlich: `GOOGLE_CLIENT_ID` **oder** `GOOGLE_CLIENT_ID_V2`
  `GOOGLE_CLIENT_SECRET` **oder** `GOOGLE_CLIENT_SECRET_V2`
  `GOOGLE_REFRESH_TOKEN`
- Optional:    `GOOGLE_TOKEN_URI` (Default: https://oauth2.googleapis.com/token)
  `GOOGLE_OAUTH_JSON` (alternativ gesamtes JSON)
- `SMTP_HOST` (optional)
- `SMTP_USER` (optional)
- `SMTP_PASS` (optional)

## Email
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASS`
- `SMTP_SECURE`
- `SMTP_FROM` (optional)
- `MAIL_FROM` (preferred; falls back to `SMTP_FROM`)
- `ALLOWLIST_EMAIL_DOMAIN` (optional)

## IMAP (optional)
- `IMAP_HOST`
- `IMAP_PORT`
- `IMAP_USER`
- `IMAP_PASS`
- `IMAP_FOLDER` (default: `INBOX`)

## Trigger Words
- `TRIGGER_WORDS_FILE` (defaults to `config/trigger_words.txt`)
