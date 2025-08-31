"""Tests for the orchestrator module."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator, feature_flags


def test_gather_triggers_normalizes_data(monkeypatch):
    events = [{"creator": "alice@example.com", "summary": "meeting preparation", "event_id": "x1"}]
    contacts = [
        {"emailAddresses": [{"value": "bob@example.com"}], "names": []}
    ]

    monkeypatch.setattr(orchestrator, "fetch_events", lambda: events)
    monkeypatch.setattr(orchestrator, "fetch_contacts", lambda: contacts)
    monkeypatch.setattr(orchestrator, "_calendar_fetch_logged", lambda wf: True)
    monkeypatch.setattr(orchestrator, "_event_id_exists", lambda eid: False)

    triggers = orchestrator.gather_triggers()

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


def test_gather_triggers_skips_events_without_trigger(monkeypatch):
    events = [{"creator": "alice@example.com", "summary": "team sync", "event_id": "x2"}]
    monkeypatch.setattr(orchestrator, "fetch_events", lambda: events)
    monkeypatch.setattr(orchestrator, "fetch_contacts", lambda: [])
    monkeypatch.setattr(orchestrator, "_calendar_fetch_logged", lambda wf: True)
    triggers = orchestrator.gather_triggers()
    assert triggers == []


def test_gather_triggers_logs_fetch(monkeypatch):
    def fake_fetch():
        orchestrator.log_step("calendar", "fetch_call", {})
        orchestrator.log_step("calendar", "raw_api_response", {"response": {}})
        orchestrator.log_step(
            "calendar",
            "fetched_events",
            {
                "count": 1,
                "time_min": "t0",
                "time_max": "t1",
                "ids": ["x"],
                "summaries": [""],
                "creator_emails": [""],
            },
        )
        return [{"event_id": "x"}]

    monkeypatch.setattr(orchestrator, "fetch_events", fake_fetch)
    monkeypatch.setattr(orchestrator, "fetch_contacts", lambda: [])
    logs = []
    original_log_step = orchestrator.log_step

    def fake_log_step(category, status, payload=None, severity="info"):
        logs.append({"category": category, "status": status, "payload": payload})
        original_log_step(category, status, payload or {}, severity=severity)

    monkeypatch.setattr(orchestrator, "log_step", fake_log_step)
    orchestrator.gather_triggers()
    statuses = [l["status"] for l in logs]
    assert {"fetch_call", "raw_api_response", "fetched_events", "fetch_return"} <= set(statuses)

def test_run_pipeline_respects_feature_flags(monkeypatch):
    monkeypatch.setattr(feature_flags, "USE_PUSH_TRIGGERS", False)
    monkeypatch.setattr(feature_flags, "ENABLE_PRO_SOURCES", False)
    monkeypatch.setattr(feature_flags, "ATTACH_PDF_TO_HUBSPOT", True)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "portal")
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)

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
        path.write_text("pdf")

    def fake_csv(data, path):
        called["csv"] += 1
        path.write_text("csv")

    def fake_upsert(data):
        called["upsert"] += 1
        return "123"

    def fake_attach(path, company_id):
        called["attach"] += 1

    trigger = {
        "source": "calendar",
        "creator": "carol@example.com",
        "recipient": "carol@example.com",
        "payload": {"event_id": "x3"},
    }

    monkeypatch.setattr(orchestrator, "gather_triggers", lambda: [trigger])
    monkeypatch.setattr(orchestrator, "_event_id_exists", lambda eid: False)
    monkeypatch.setattr(orchestrator, "_missing_required", lambda s, p: [])

    orchestrator.run(
        researchers=[basic, pro],
        consolidate_fn=fake_consolidate,
        pdf_renderer=fake_pdf,
        csv_exporter=fake_csv,
        hubspot_upsert=fake_upsert,
        hubspot_attach=fake_attach,
        hubspot_check_existing=lambda cid: None,
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
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)

    gathered = {"called": False}

    def fake_gather(*args, **kwargs):  # pragma: no cover - simple stub
        gathered["called"] = True
        return []

    monkeypatch.setattr(orchestrator, "gather_triggers", fake_gather)

    with pytest.raises(SystemExit) as exc:
        orchestrator.run(
            researchers=[],
            consolidate_fn=lambda x: x,
            pdf_renderer=lambda d, p: None,
            csv_exporter=lambda d, p: None,
            hubspot_upsert=lambda d: None,
            hubspot_attach=lambda p: None,
        )

    assert exc.value.code == 0
    assert not gathered["called"]


def test_run_skips_processing_when_duplicate(monkeypatch):
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)
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

