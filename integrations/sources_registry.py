"""Registry of data sources."""

from agents import (
    agent_internal_search,
    agent_external_level1_company_search,
    agent_external_level2_companies_search,
    agent_internal_level2_company_search,
    agent_internal_customer_research,
)

SOURCES = [
    agent_internal_search.run,
    agent_external_level1_company_search.run,
    agent_external_level2_companies_search.run,
    agent_internal_level2_company_search.run,
    agent_internal_customer_research.run,
]
