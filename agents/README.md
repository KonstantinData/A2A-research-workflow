# Agents

## Purpose
The agents package contains the modular researchers that power the account-to-account
workflow.  Each agent focuses on a specific stage of the investigation pipeline:
locating candidate organisations, enriching company profiles, verifying internal
CRM records, notifying employees and building digest artefacts.  The modules are
written to the common normalized schema (``{"source", "creator", "recipient", "payload"}``)
so the orchestrator can chain them together without bespoke glue code.  External
agents query curated static datasets to seed the research, whereas the internal
agents talk to live HubSpot endpoints and auxiliary services to gather customer
context and keep artefacts in sync.

## Files
### Top-level agents and helpers
- `__init__.py`: package marker that exposes shared utilities for agent imports.
- `agent_company_detail_research.py`: enriches a single company with static details and
  optional HubSpot attachments, writing a cached JSON artefact alongside the workflow log.
- `agent_external_level1_company_search.py`: proposes first-level neighbouring companies
  for further research and logs the result set for downstream steps.
- `agent_external_level2_companies_search.py`: expands the search to related branches and
  business units once level-1 candidates have been identified.
- `agent_internal_level2_company_search.py`: enriches the second-level neighbour list using
  the curated static dataset so that downstream steps have domain and classification hints.
- `agent_internal_customer_research.py`: summarises the artefacts produced by the level-2
  agents and turns them into concise customer notes for analysts.
- `agent_internal_search.py`: orchestrates the legacy internal workflow, validating input,
  delegating to the new internal company pipeline and raising reminder tasks when fields
  are missing.
- `company_data.py`: houses the curated static dataset used by the external agents when
  no live CRM information is available.
- `digest.py`: formats completed research payloads into short-form digests for email or
  chat delivery.
- `email_listener.py`: event hook that ingests mailbox updates and triggers follow-up
  research where required.
- `field_completion_agent.py`: extracts missing company names and domains from free-form
  text using regex heuristics or optional OpenAI completions before logging the outcome.
- `recovery_agent.py`: fallback workflow that reconstructs artefacts from persisted JSONL
  logs in case the main orchestrator crashes mid-run.
- `reminder_service.py`: cron-friendly helper that emails outstanding reminders to
  employees whose input is required to finish a research ticket.
- `templates.py`: centralised Jinja templates used by digest, reminder and email agents.
- `internal_company/`: subpackage implementing the live HubSpot-backed internal company
  research pipeline.

### `internal_company` subpackage
- `internal_company/__init__.py`: declares the namespace for plugin registration.
- `internal_company/fetch.py`: retrieves and caches HubSpot company data, with optional
  Redis-based caching and a static dataset fallback for tests.  Also resolves neighbour
  suggestions and recent report attachments.
- `internal_company/normalize.py`: validates and normalises raw HubSpot responses into the
  shared schema, ensuring mandatory payload fields are present for the orchestrator.
- `internal_company/plugins.py`: lightweight plugin registry allowing additional fetch /
  normalize implementations to be registered alongside the default source.
- `internal_company/run.py`: orchestrates the registered plugins, persists validated
  results to graph storage when enabled, and requests missing fields from employees via
  task creation and email notifications.

## Dependencies
The agents rely on a small set of shared infrastructure modules:
- `config.settings.SETTINGS` supplies directories for artefacts and workflow logs as well
  as feature flags such as graph storage and static dataset toggles.
- `integrations.hubspot_api` is the primary CRM interface used by the internal agents to
  retrieve companies, contacts, reports and neighbour suggestions.
- `integrations.email_sender` and `core.tasks` are used to notify employees when manual
  input is required to complete a research ticket.
- `integrations.graph_storage` persists successful internal research payloads when the
  feature flag is enabled.
- `a2a_logging.jsonl_sink.append` is imported dynamically to emit structured workflow
  events for observability.
- Optional third-party dependencies include `redis` for distributed caching and standard
  libraries such as `json`, `pathlib`, `datetime` and `dataclasses`.

## Usage
All agents expose a `run(trigger: Dict[str, Any]) -> Dict[str, Any]` entry point.  The
`trigger` must contain `creator` and `recipient` metadata along with a `payload` that
includes the company context (for example `company_name`, `company_domain`, industry
information or CRM identifiers).  External agents can be invoked directly to populate the
initial candidate list:

```python
from agents import agent_external_level1_company_search
result = agent_external_level1_company_search.run({
    "creator": {"service": "orchestrator"},
    "recipient": {"email": "analyst@example.com"},
    "payload": {"company_name": "Example Corp"},
})
```

Internal research is coordinated via `agents.internal_company.run.run`, which executes all
registered plugins, validates the result and optionally persists it:

```python
from agents.internal_company import run as internal_run
normalized = internal_run.run(trigger)
```

In production these `run` functions are orchestrated by the workflow engine, but they can
be executed manually for debugging or during unit tests.  Artefacts are written to the
folders configured by `SETTINGS`, so ensure those directories exist when running agents
outside the managed environment.
