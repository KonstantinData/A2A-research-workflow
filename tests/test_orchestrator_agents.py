import json
from pathlib import Path

from core import orchestrator
from agents import (
    agent_internal_search,
    agent_internal_level2_company_search,
    agent_company_detail_research,
    agent_external_level1_company_search,
    agent_external_level2_companies_search,
)


def _trigger():
    return {
        "source": "calendar",
        "creator": "a@example.com",
        "recipient": "a@example.com",
        "payload": {
            "company": "ACME",
            "domain": "acme.com",
            "email": "a@example.com",
            "phone": "1",
        },
    }


def test_all_agents_called(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls = []

    def stub(name):
        def _run(trig):
            calls.append(name)
            return {"payload": {name: True}}
        return _run

    monkeypatch.setattr(agent_internal_search, "run", stub("internal_search"))
    monkeypatch.setattr(agent_internal_level2_company_search, "run", stub("internal_level2"))
    monkeypatch.setattr(agent_company_detail_research, "run", stub("company_detail"))
    monkeypatch.setattr(agent_external_level1_company_search, "run", stub("external_l1"))
    monkeypatch.setattr(agent_external_level2_companies_search, "run", stub("external_l2"))
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda **k: None)

    trig = _trigger()
    orchestrator.run(triggers=[trig])

    assert calls == [
        "internal_search",
        "external_l1",
        "external_l2",
        "internal_level2",
        "company_detail",
    ]
    for name in calls:
        assert trig["payload"][name] is True
