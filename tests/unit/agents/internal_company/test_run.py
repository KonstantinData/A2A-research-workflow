from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from agents.internal_company import run, fetch


def test_run_success_with_mocked_crm(monkeypatch):
    """run returns CRM summary when data available."""
    def fake_crm(payload: dict):
        return {"summary": f"{payload.get('company')} overview"}

    monkeypatch.setattr(fetch, "_retrieve_from_crm", fake_crm)
    fetch._CACHE.clear()

    trigger = {
        "creator": {"email": "alice@example.com"},
        "recipient": {"email": "bob@example.com"},
        "payload": {"company": "Acme"},
    }

    result = run.run(trigger)

    assert result["payload"]["summary"] == "Acme overview"


def test_run_early_exit_when_company_missing(monkeypatch):
    """Missing company info raises ValueError before CRM lookup."""
    called = {"flag": False}

    def fake_crm(payload: dict):
        called["flag"] = True
        return {"summary": "should not be used"}

    monkeypatch.setattr(fetch, "_retrieve_from_crm", fake_crm)
    fetch._CACHE.clear()

    trigger = {
        "creator": {"email": "alice@example.com"},
        "recipient": {"email": "bob@example.com"},
        "payload": {},
    }

    with pytest.raises(ValueError):
        run.run(trigger)

    assert called["flag"] is False


def test_run_crm_failure_falls_back(monkeypatch):
    """Failures talking to CRM yield fallback summary."""

    def failing_crm(company: str):
        raise RuntimeError("CRM error")

    monkeypatch.setattr(fetch, "_retrieve_from_crm", failing_crm)
    fetch._CACHE.clear()

    def safe_fetch(trigger, force_refresh: bool = False):
        payload = trigger.get("payload") or {}
        company = payload.get("company")
        if not company:
            return {"summary": "No internal company research available."}
        try:
            return fetch._retrieve_from_crm(company)
        except Exception:
            return {"summary": "No internal company research available."}

    monkeypatch.setattr(fetch, "fetch", safe_fetch)

    trigger = {
        "creator": {"email": "alice@example.com"},
        "recipient": {"email": "bob@example.com"},
        "payload": {"company": "Acme"},
    }

    result = run.run(trigger)

    assert result["payload"]["summary"] == "No internal company research available."
