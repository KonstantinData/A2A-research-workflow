"""Registry of research source callables used across the workflow."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from agents import (
    agent_company_detail_research,
    agent_external_level1_company_search,
    agent_external_level2_companies_search,
    agent_internal_level2_company_search,
    agent_internal_search,
)

SourceCallable = Callable[[Dict[str, Any]], Dict[str, Any]]

SOURCES: List[SourceCallable] = [
    agent_internal_search.run,
    agent_external_level1_company_search.run,
    agent_external_level2_companies_search.run,
    agent_internal_level2_company_search.run,
    agent_company_detail_research.run,
]

__all__ = ["SOURCES"]
