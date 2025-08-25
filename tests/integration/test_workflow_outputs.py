"""Integration tests for PDF/CSV generation and HubSpot hooks."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator, feature_flags
from output import pdf_render, csv_export


def test_orchestrator_generates_outputs_and_calls_hubspot(tmp_path, monkeypatch, company_acme):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USE_PUSH_TRIGGERS", "1")
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "portal")
    # reload feature flags to pick up env change
    monkeypatch.setattr(feature_flags, "USE_PUSH_TRIGGERS", True)

    calls = {"upsert": 0, "attach": 0}

    def fake_upsert(data):
        calls["upsert"] += 1

    def fake_attach(path, company_id):
        calls["attach"] += 1

    triggers = []

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
    )

    out_dir = Path("output/exports")
    assert (out_dir / "report.pdf").exists()
    assert (out_dir / "data.csv").exists()
    assert calls["upsert"] == 1
    assert calls["attach"] == 1
