# Integrations

## Purpose
Clients for external services such as HubSpot and Google APIs.

## Files
- `hubspot_api.py`
- `google_calendar.py`: scheduled polling of events with trigger-word filtering and normalized payloads.
- `google_contacts.py`: scheduled polling of contacts with trigger-word filtering and normalized payloads.
- `email_sender.py`: SMTP e-mail helper.
- `web_scraper.py`
- `sources_registry.py`
- `templates/`: reusable e-mail templates.

## Dependencies
`google-api-python-client`, `google-auth`, standard library SMTP.

## Usage
Modules are imported by the orchestrator or other components to interact with external services.
