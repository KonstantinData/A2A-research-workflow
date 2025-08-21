
# Configuration

Document environment variables and secrets required for the workflow.
See the main repository `README.md` for additional context.

## Email

These variables are used for email notifications via SMTP:

- `MAIL_FROM`
- `MAIL_USER`
- `MAIL_SMTP_HOST`
- `MAIL_SMTP_PORT`
- `MAIL_SMTP_SECURE`
- `MAIL_SMTP_PASS`

## Trigger Words

- `TRIGGER_WORDS_FILE`: Optional override for the trigger word list.
  Defaults to `config/trigger_words.txt` if not set.

## GitHub (optional)

Used for error tracking via GitHub issues:

- `GITHUB_REPOSITORY` (format: `owner/repo`)
- `GITHUB_TOKEN`: GitHub token with `repo` scope

## Google API

Used for Google Calendar and Contacts integration:

- `GOOGLE_CREDENTIALS_JSON_BASE64`: Base64-encoded service account or OAuth token
- `GOOGLE_CALENDAR_ID` (optional)
