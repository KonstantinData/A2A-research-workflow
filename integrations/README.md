
# Integrations

## Purpose

Clients for external services such as HubSpot and Google APIs.

## Files

- `hubspot_api.py`: Stub for HubSpot upsert and file attachment.
- `google_calendar.py`: Scheduled polling of calendar events with trigger-word filtering and normalized payloads.
- `google_contacts.py`: Scheduled polling of contacts with trigger-word filtering and normalized payloads.
- `email_sender.py`: SMTP e-mail helper.
- `web_scraper.py`: Web scraping utilities (if applicable).
- `sources_registry.py`: Registry for data sources used by researchers.
- `templates/`: Reusable e-mail templates.

## External APIs

These modules will later interface with respective APIs; currently some are placeholders (stubs).

## Dependencies

- [`google-api-python-client`](https://pypi.org/project/google-api-python-client/)
- [`google-auth`](https://pypi.org/project/google-auth/)
- Standard library: `smtplib`, `email`, etc.

## Usage

Modules are imported by the orchestrator or other components to interact with external services.

Configuration is done via environment variables, e.g.:

- `GOOGLE_CREDENTIALS_JSON_BASE64`
- `GOOGLE_CALENDAR_ID`
- `MAIL_TO`
