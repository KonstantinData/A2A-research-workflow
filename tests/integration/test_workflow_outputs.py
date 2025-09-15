"""Integration tests for PDF/CSV generation and HubSpot hooks."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator
from config.settings import SETTINGS
from output import pdf_render, csv_export


def test_orchestrator_generates_outputs_and_calls_hubspot(tmp_path, monkeypatch, company_acme):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USE_PUSH_TRIGGERS", "1")
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "token")
    monkeypatch.setenv("LIVE_MODE", "0")
    # reload settings to pick up env change
    monkeypatch.setattr(SETTINGS, "use_push_triggers", True)

    calls = {"upsert": 0, "attach": 0}

    def fake_upsert(data):
        calls["upsert"] += 1
        return "123"

    def fake_attach(path, company_id):
        calls["attach"] += 1

    triggers = [
        {
            "source": "calendar",
            "creator": "alice@example.com",
            "recipient": "alice@example.com",
            "payload": {},
        }
    ]

    def researcher(trigger):
        return {
            "source": "researcher",
            "payload": {"company": company_acme["name"]},
        }

    def consolidate_fn(results):
        return {"company": company_acme["name"], "meta": {"company": {"source": "researcher", "last_verified_at": "now"}}}

    # Avoid real SMTP by stubbing out email sending.
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)

    orchestrator.run(
        triggers=triggers,
        researchers=[researcher],
        consolidate_fn=consolidate_fn,
        pdf_renderer=pdf_render.render_pdf,
        csv_exporter=csv_export.export_csv,
        hubspot_upsert=fake_upsert,
        hubspot_attach=fake_attach,
        hubspot_check_existing=lambda cid: None,
    )

    out_dir = SETTINGS.exports_dir
    assert (out_dir / "report.pdf").exists()
    assert (out_dir / "data.csv").exists()
    assert calls["upsert"] == 1
    assert calls["attach"] == 1
