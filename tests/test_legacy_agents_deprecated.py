import importlib

import pytest


@pytest.mark.parametrize(
    "mod",
    [
        "agents.autonomous_report_agent",
        "agents.autonomous_email_agent",
        "agents.autonomous_research_agent",
    ],
)
def test_deprecated(mod):
    with pytest.raises(RuntimeError):
        importlib.import_module(mod)
