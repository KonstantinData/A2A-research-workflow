from pathlib import Path

import pytest

try:  # pragma: no cover - guard legacy consolidate module
    from core import consolidate
except ImportError:  # pragma: no cover - legacy module removed
    pytestmark = pytest.mark.skip(
        reason="Legacy consolidate/agents workflow removed; migrate to app services"
    )
else:
    from agents import (
        agent_internal_search,
        agent_external_level1_company_search,
        agent_external_level2_companies_search,
        agent_internal_level2_company_search,
        agent_company_detail_research,
    )


def test_neighbor_integration(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    # stub internal_run to provide neighbors without existing report
    def _internal_stub(trig):
        return {
            "payload": {
                "exists": False,
                "neighbors": [
                    {
                        "company_name": "Globex Corp",
                        "company_domain": "globex.com",
                        "description": "manufacturing",
                    }
                ],
            }
        }

    monkeypatch.setattr(agent_internal_search, "internal_run", _internal_stub)
    monkeypatch.setattr(agent_internal_search.email_sender, "send_email", lambda **k: None)

    trig = {
        "source": "calendar",
        "creator": "a@example.com",
        "recipient": "a@example.com",
        "payload": {
            "company": "Acme GmbH",
            "domain": "acme.com",
            "email": "a@example.com",
            "phone": "1",
            "event_id": "E1",
        },
    }

    res_int = agent_internal_search.run(trig)
    trig["payload"].update(res_int["payload"])

    res_l1 = agent_external_level1_company_search.run(trig)
    trig["payload"].update(res_l1["payload"])

    res_l2 = agent_external_level2_companies_search.run(trig)
    trig["payload"].update(res_l2["payload"])

    res_int_l2 = agent_internal_level2_company_search.run(trig)
    trig["payload"].update(res_int_l2["payload"])

    res_det = agent_company_detail_research.run(trig)

    combined = consolidate.consolidate([
        res_int,
        res_l1,
        res_l2,
        res_int_l2,
        res_det,
    ])

    assert combined.get("neighbor_level1"), "level1 neighbors missing"
    assert combined.get("neighbor_level2"), "level2 neighbors missing"
