from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.internal_company import fetch


def test_fetch_caches_by_company(monkeypatch, company_acme, company_globex):
    calls = {"count": 0}

    def fake_crm(company):
        calls["count"] += 1
        return {"summary": company}

    monkeypatch.setattr(fetch, "_retrieve_from_crm", fake_crm)
    fetch._CACHE.clear()

    trigger_acme = {"payload": {"company": company_acme["name"]}}
    trigger_globex = {"payload": {"company": company_globex["name"]}}

    # First call for Acme hits CRM, second is served from cache
    fetch.fetch(trigger_acme)
    fetch.fetch(trigger_acme)

    # Different company triggers a new CRM call
    fetch.fetch(trigger_globex)

    assert calls["count"] == 2

    # Force refresh should bypass cache
    fetch.fetch(trigger_acme, force_refresh=True)
    assert calls["count"] == 3


def test_fetch_cache_expires(monkeypatch, company_acme):
    calls = {"count": 0}

    def fake_crm(company):
        calls["count"] += 1
        return {"summary": company}

    monkeypatch.setattr(fetch, "_retrieve_from_crm", fake_crm)
    monkeypatch.setattr(fetch, "CACHE_TTL_SECONDS", 1)
    fetch._CACHE.clear()

    trigger = {"payload": {"company": company_acme["name"]}}

    fetch.fetch(trigger)
    time.sleep(1.1)
    fetch.fetch(trigger)

    assert calls["count"] == 2
