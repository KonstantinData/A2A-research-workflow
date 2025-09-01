# A2A-research-workflow

Automated Agent-to-Agent (A2A) research workflow for company data enrichment, HubSpot integration, and standardized PDF/CSV reporting using Python and GitHub Actions.

The workflow operates exclusively in live mode and requires valid credentials for Google Calendar, Google Contacts, HubSpot, and an SMTP server.

## Project Overview

This repository provides a skeleton implementation of the A2A research workflow. It orchestrates multiple research agents, consolidates their results, and produces PDF and CSV dossiers. HubSpot integration and Google Calendar/Contacts triggers are prepared but not yet fully implemented.

## Architecture

```mermaid
flowchart LR
    GC[Google Calendar] -->|triggers| O[Orchestrator]
    GCo[Google Contacts] -->|triggers| O
    O -->|dispatch| A[Research Agents]
    A --> C[Consolidation]
    C --> P[PDF/CSV]
    C --> H[HubSpot]
    P --> E[Email]
```

## Setup Instructions

1. Create and activate a Python 3.11 environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set required environment variables as needed. SMTP/IMAP/HubSpot/Google variables are listed in [`.env.example`](.env.example) and documented in [`ops/CONFIG.md`](ops/CONFIG.md).
4. Adjust trigger words in `config/trigger_words.txt` or point `TRIGGER_WORDS_FILE` to a custom list.

## LIVE Setup

1. Copy [`.env.example`](.env.example) to `.env` and fill in the credentials (SMTP/IMAP/HubSpot/Google variables see [`ops/CONFIG.md`](ops/CONFIG.md)).
2. Start the orchestrator with Docker Compose:
   ```bash
   docker compose -f ops/docker-compose.yml up
   ```
3. For scheduled runs via GitHub Actions, define repository secrets:
   - `GOOGLE_CLIENT_ID_V2`
   - `GOOGLE_CLIENT_SECRET_V2`
   - `GOOGLE_REFRESH_TOKEN`
   - `HUBSPOT_ACCESS_TOKEN`
   - `HUBSPOT_PORTAL_ID`
   - `SMTP_HOST`
   - `SMTP_PORT`
   - `SMTP_USER`
   - `SMTP_PASS`
   - `SMTP_SECURE`
   - `SMTP_FROM`

PDF generation relies on WeasyPrint system libraries, installed by the Dockerfile and the CI workflow.

## Google OAuth & Token Rotation

The refresh token is bound to the exact client (ID/secret); mixing clients causes `invalid_grant` errors. To re-issue a refresh token, generate a consent URL with `access_type=offline` and `prompt=consent`. Only the v2 client (`GOOGLE_CLIENT_ID_V2`/`GOOGLE_CLIENT_SECRET_V2`) is supported.

## LIVE mode

`LIVE_MODE=1` (default) hard-fails when Google OAuth, SMTP or HubSpot configuration is missing. The calendar integration probes the token/client pair and may log `invalid_grant` if the refresh token was revoked or belongs to a different client. Re-issue the token with `access_type=offline` and `prompt=consent`.

## Workflow Description

1. Poll Google Calendar and Contacts for new entries containing trigger words.
2. Normalize each trigger with its creator e‑mail and source.
3. Run duplicate checks in HubSpot.
4. Execute research agents and classify results.
5. Consolidate data and generate PDF/CSV outputs.
6. Optionally enrich HubSpot with core fields and attach the PDF.

## Data Model

### Two‑Layer Company Model

The research workflow distinguishes between **core company data** and
**HubSpot‑specific data**.  This separation enables the project to
remain portable – you can reuse the core model with other CRMs or data
pipelines – while still populating all available fields in HubSpot.

1. **Core Schema** – The universal, lean representation of a company
   that is independent of any CRM.  Required fields are:

   | Field | Description |
   | --- | --- |
   | `company_name` | Official company name |
   | `domain` | Company web domain (without protocol) |
   | `industry_group` | High‑level industry cluster such as “Manufacturing” or “Energy” |
   | `industry` | Specific sector or market focus, e.g. “Renewable Energy” |
   | `description` | Free‑text description from notes or agent research |

   Optional fields include `contact_info` (email, phone), `country`
   (ISO‑3166 code) and `classification` (mapping to WZ/NACE/ISIC).  No
   sales‑specific fields (owner, revenue, etc.) live in the core model.

2. **HubSpot Mapping Layer** – A separate dictionary of CRM‑specific
   properties.  When a report is synced to HubSpot, the core fields
   are mapped onto HubSpot property names (see
   [`docs/hubspot_mapping.md`](docs/hubspot_mapping.md) for details).
   Additional fields such as `city`, `postal_code`, `number_of_employees`,
   `total_revenue`, `lead_status` or `ideal_customer_profile_tier` are
   optional and can be supplied via this layer.  A set of
   `company_keywords` is automatically generated from the core
   `industry` and `description` to aid search in HubSpot.  The mapping
   occurs exclusively in `integrations/hubspot_api.py` and is decoupled
   from the agents and orchestrator.

### Rationale for Dropping Classification Numbers

Earlier versions of this project relied on economic classification numbers (e.g. WZ 2008,
NACE, ÖNACE, NOGA) to categorise companies.  While these codes are useful for
statistical analysis, they are opaque to most business users, evolve over
time and differ across jurisdictions.  Maintaining mappings between
multiple classification systems introduces friction and slows down
automation.

To simplify the research workflow the core company model has been
refactored.  Agents that research or compare companies now rely on
`industry_group`, `industry` and `description` as their primary
criteria.  The earlier classification numbers are added only when
needed for backward compatibility via the optional `classification`
field.

### Example Core & HubSpot Structure

After consolidating the outputs of the research agents you will obtain
a core record such as:

```json
{
  "company_name": "SolarTech GmbH",
  "domain": "solartech.de",
  "industry_group": "Energy",
  "industry": "Renewable Energy",
  "description": "Solar panel manufacturer with focus on B2B distribution",
  "contact_info": {"email": "info@solartech.de", "phone": "+49 89 123456"},
  "country": "DE"
}
```

If you wish to enrich HubSpot with additional details you can add a
`hubspot` section:

```json
{
  "core": {
    "company_name": "SolarTech GmbH",
    "domain": "solartech.de",
    "industry_group": "Energy",
    "industry": "Renewable Energy",
    "description": "Solar panel manufacturer with focus on B2B distribution"
  },
  "hubspot": {
    "city": "Munich",
    "postal_code": "80331",
    "number_of_employees": 250,
    "total_revenue": "45000000",
    "lead_status": "Open",
    "company_owner": "Max Mustermann",
    "ideal_customer_profile_tier": "Tier 1"
  }
}
```

Only the core section is used to produce the PDF/CSV reports.  The
`hubspot` section is consumed by `upsert_company()` to feed the HubSpot
CRM.

## Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `SMTP_HOST` | SMTP server hostname | – |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_USER` | SMTP username | – |
| `SMTP_PASS` | SMTP password | – |
| `SMTP_FROM` | Sender e‑mail address | `SMTP_USER` |
| `SMTP_SECURE` | SMTP security mode (`ssl`/`starttls`) | `ssl` |
| `ALLOWLIST_EMAIL_DOMAIN` | Allow reminder emails only to addresses in this domain | – |
| `MAIL_TO` | Recipient e‑mail for reports | – |
| `TRIGGER_WORDS_FILE` | Path to trigger words list | `config/trigger_words.txt` |
| `GOOGLE_CLIENT_ID_V2` | Google OAuth client ID | – |
| `GOOGLE_CLIENT_SECRET_V2` | Google OAuth client secret | – |
| `GOOGLE_REFRESH_TOKEN` | Google OAuth refresh token | – |
| `GOOGLE_CALENDAR_IDS` | Comma-separated calendar IDs to poll | `primary` |
| `CAL_LOOKAHEAD_DAYS` | Days ahead to fetch events | `14` |
| `CAL_LOOKBACK_DAYS` | Days back to include events | `1` |
| `HUBSPOT_ACCESS_TOKEN` | HubSpot private app token | – |
| `USE_PUSH_TRIGGERS` | Disable scheduled polling | `false` |
| `ENABLE_PRO_SOURCES` | Allow pro research agents | `false` |
| `ATTACH_PDF_TO_HUBSPOT` | Upload PDF to HubSpot | `true` |
| `USE_GCP` | Enable Google Cloud features | `false` |
| `RUN_ID` | Identifier for logging | random UUID |
| `STAGE` | Logging stage label | – |
| `GITHUB_REPOSITORY` | Repository for error issues | – |
| `GITHUB_TOKEN` | Token for GitHub issue creation | – |

## Repository Structure

Key directories:

- `agents/` – individual research agents.
- `core/` – orchestration, classification, consolidation, and feature flags.
- `integrations/` – external service clients (HubSpot, Google, email) and templates.
- `output/` – PDF and CSV rendering utilities.
- `schemas/` – JSON schema definitions.
- `compliance/` – GDPR helpers.
- `logging/` – logging utilities and error definitions.
- `tests/` – unit, integration, and end-to-end tests.
- `ops/` – operational files such as Dockerfile and CI/CD configs.
- `config/` – configuration files such as trigger word list.
## License

MIT
