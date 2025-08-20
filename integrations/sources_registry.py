"""Registry of data sources."""

from agents import (
    agent1_internal_company_research,
    agent2_company_search,
    agent3_external_branch_research,
    agent4_external_customer_research,
    agent5_internal_customer_research,
)

SOURCES = [
    agent1_internal_company_research.run,
    agent2_company_search.run,
    agent3_external_branch_research.run,
    agent4_external_customer_research.run,
    agent5_internal_customer_research.run,
]
