# Agents

## Purpose
Modular research agents gather company information from various sources. Each
agent exposes a `run` function returning structured data.

## Files
- `agent_internal_search.py`: stub for internal research.
- `agent_external_level1_company_search.py`: search companies by classification.
- `agent_external_level2_companies_search.py`: external branch research.
- `agent_internal_level2_company_search.py`: external customer research.
- `agent_internal_customer_research.py`: internal customer research.

## Dependencies
Standard library only.

## Usage
Agents are invoked by the orchestrator and share a common input/output schema.
