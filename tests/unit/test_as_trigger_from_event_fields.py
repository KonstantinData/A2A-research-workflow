from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator


def test_trigger_from_location_or_attendee():
    ev = {"summary": "Weekly sync", "description": "", "location": "Meeting Vorbereitung"}
    assert orchestrator._as_trigger_from_event(ev) is not None
    ev2 = {"summary": "Weekly", "description": "", "attendees": [{"email": "research@foo.com"}]}
    # depends on words list; at least code path handles dict
    orchestrator._as_trigger_from_event(ev2)  # should not raise


def test_no_enriched_log_when_fields_present(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    trig = {
        "source": "calendar",
        "creator": "alice@example.com",
        "recipient": "alice@example.com",
        "payload": {
            "event_id": "e1",
            "company_name": "ACME",
            "domain": "acme.com",
        },
    }
    monkeypatch.setattr(
        orchestrator.field_completion_agent,
        "run",
        lambda t: {"company_name": "ACME", "domain": "acme.com"},
    )
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)
    monkeypatch.setenv("A2A_TEST_MODE", "1")

    orchestrator.run(
        triggers=[trig],
        researchers=[],
        consolidate_fn=lambda r: {},
        pdf_renderer=lambda data, path: path.write_text("pdf"),
        csv_exporter=lambda data, path: path.write_text("csv"),
        hubspot_upsert=lambda d: None,
        hubspot_attach=lambda p, c: None,
        hubspot_check_existing=lambda cid: None,
    )

    logs = "".join(p.read_text() for p in Path("logs/workflows").glob("*.jsonl"))
    assert '"status": "enriched_by_ai"' not in logs
