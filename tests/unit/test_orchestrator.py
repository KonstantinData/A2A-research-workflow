"""Tests for the orchestrator module."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator, feature_flags


def test_gather_triggers_normalizes_data():
    events = [{"creator": "alice@example.com", "summary": "Test"}]
    contacts = [
        {"emailAddresses": [{"value": "bob@example.com"}], "names": []}
    ]

    triggers = orchestrator.gather_triggers(lambda: events, lambda: contacts)

    assert triggers == [
        {
            "source": "calendar",
            "creator": "alice@example.com",
            "recipient": "alice@example.com",
            "payload": events[0],
        },
        {
            "source": "contacts",
            "creator": "bob@example.com",
            "recipient": "bob@example.com",
            "payload": contacts[0],
        },
    ]
def test_run_pipeline_respects_feature_flags(monkeypatch):
    monkeypatch.setattr(feature_flags, "USE_PUSH_TRIGGERS", False)
    monkeypatch.setattr(feature_flags, "ENABLE_PRO_SOURCES", False)
    monkeypatch.setattr(feature_flags, "ATTACH_PDF_TO_HUBSPOT", True)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "portal")

    events = [{"creator": "carol@example.com"}]
    contacts = []

    called = {"basic": 0, "pro": 0, "pdf": 0, "csv": 0, "upsert": 0, "attach": 0}

    def basic(trigger):
        called["basic"] += 1
        return {"basic": True}

    def pro(trigger):
        called["pro"] += 1
        return {"pro": True}

    pro.pro = True  # mark as pro-only

    def fake_consolidate(results):
        return {"results": results}

    def fake_pdf(data, path):
        called["pdf"] += 1

    def fake_csv(data, path):
        called["csv"] += 1

    def fake_upsert(data):
        called["upsert"] += 1

    def fake_attach(path, company_id):
        called["attach"] += 1

    orchestrator.run(
        event_fetcher=lambda: events,
        contact_fetcher=lambda: contacts,
        researchers=[basic, pro],
        consolidate_fn=fake_consolidate,
        pdf_renderer=fake_pdf,
        csv_exporter=fake_csv,
        hubspot_upsert=fake_upsert,
        hubspot_attach=fake_attach,
    )

    assert called["basic"] == 1
    assert called["pro"] == 0
    assert called["pdf"] == 1
    assert called["csv"] == 1
    assert called["upsert"] == 1
    assert called["attach"] == 1


def test_run_skips_intake_when_push_triggers_enabled(monkeypatch):
    monkeypatch.setattr(feature_flags, "USE_PUSH_TRIGGERS", True)
    monkeypatch.setattr(feature_flags, "ENABLE_PRO_SOURCES", False)
    monkeypatch.setattr(feature_flags, "ATTACH_PDF_TO_HUBSPOT", False)

    gathered = {"called": False}

    def fake_gather(*args, **kwargs):  # pragma: no cover - simple stub
        gathered["called"] = True
        return []

    monkeypatch.setattr(orchestrator, "gather_triggers", fake_gather)

    orchestrator.run(
        researchers=[],
        consolidate_fn=lambda x: x,
        pdf_renderer=lambda d, p: None,
        csv_exporter=lambda d, p: None,
        hubspot_upsert=lambda d: None,
        hubspot_attach=lambda p: None,
    )

    assert not gathered["called"]


def test_run_skips_processing_when_duplicate():
    triggers = [
        {
            "source": "calendar",
            "creator": "alice@example.com",
            "recipient": "alice@example.com",
            "payload": {},
        }
    ]

    calls = {"pdf": 0, "csv": 0, "upsert": 0, "attach": 0}

    def consolidate_fn(results):
        return {"name": "Acme"}

    def fake_pdf(data, path):
        calls["pdf"] += 1

    def fake_csv(data, path):
        calls["csv"] += 1

    def fake_upsert(data):
        calls["upsert"] += 1

    def fake_attach(path, company_id):
        calls["attach"] += 1

    result = orchestrator.run(
        triggers=triggers,
        researchers=[],
        consolidate_fn=consolidate_fn,
        pdf_renderer=fake_pdf,
        csv_exporter=fake_csv,
        hubspot_upsert=fake_upsert,
        hubspot_attach=fake_attach,
        duplicate_checker=lambda rec, existing: True,
    )

    assert result == {"name": "Acme"}
    assert calls == {"pdf": 0, "csv": 0, "upsert": 0, "attach": 0}

