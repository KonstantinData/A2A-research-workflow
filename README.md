# A2A-research-workflow

Automated Agent-to-Agent (A2A) research workflow for company data enrichment, HubSpot integration, and standardized PDF/CSV reporting using Python, GitHub Actions, AWS, and Docker.

## Project Overview

This repository provides a skeleton implementation of the A2A research workflow. It orchestrates multiple research agents, consolidates their results, and produces PDF and CSV dossiers. HubSpot integration and Google Calendar/Contacts triggers are prepared but not yet fully implemented.

## Setup Instructions

1. Create and activate a Python 3.11 environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set required environment variables as needed (see `ops/CONFIG.md`).

## Workflow Description

1. Poll Google Calendar and Contacts for new entries containing trigger words.
2. Run duplicate checks in HubSpot.
3. Execute research agents and classify results.
4. Consolidate data and generate PDF/CSV outputs.
5. Optionally enrich HubSpot with core fields and attach the PDF.

## Example Run

```bash
python core/orchestrator.py --company "Acme GmbH" --website "https://acme.example"
```

This will generate a JSON object and demonstrate PDF/CSV export (placeholders in this skeleton).

## Repository Structure

Key directories:

- `agents/` – individual research agents.
- `core/` – orchestration, classification, consolidation, and feature flags.
- `integrations/` – external service clients (HubSpot, Google, email).
- `output/` – PDF and CSV rendering utilities.
- `schemas/` – JSON schema definitions.
- `compliance/` – GDPR helpers.
- `logging/` – logging utilities and error definitions.
- `tests/` – unit, integration, and end-to-end tests.
- `ops/` – operational files such as Dockerfile and CI/CD configs.
- `config/` – configuration files such as trigger word list.

## License

MIT
