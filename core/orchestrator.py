import os
import sys
import json
import argparse
import logging
from pathlib import Path

from integrations.google_calendar import normalize_event, fetch_events
from integrations.google_contacts import normalize_contact, fetch_contacts
from integrations import feature_flags
from integrations import email_sender  # ✅ hinzugefügt

logger = logging.getLogger(__name__)


def log_event(record: dict):
    """
    Minimal stub for logging events (required by tests).
    In production this could append to JSONL or DB.
    """
    logger.info(f"Log event: {record}")
    return record


def gather_triggers(fetch_calendar=fetch_events, fetch_contacts=fetch_contacts):
    """Collect triggers from Google Calendar and Contacts."""
    triggers = []

    try:
        for ev in fetch_calendar() or []:
            trig = normalize_event(
                ev,
                detected_trigger="meeting-vorbereitung",
                creator_email=ev.get("creator", {}).get("email"),
                creator_name=ev.get("creator", {}).get("displayName"),
            )
            triggers.append(trig)
    except Exception as e:
        logger.warning(f"Calendar fetch failed: {e}")

    try:
        for c in fetch_contacts() or []:
            trig = normalize_contact(c)
            triggers.append(trig)
    except Exception as e:
        logger.warning(f"Contacts fetch failed: {e}")

    return triggers


def run_pipeline(triggers, researcher, consolidate_fn, hubspot_client):
    """
    Core orchestration: run researcher → consolidate → upload to HubSpot.
    """
    results = []
    for trig in triggers:
        try:
            result = researcher(trig)
            results.append(result)
        except Exception as e:
            logger.error(f"Researcher failed for {trig}: {e}")
            continue

    consolidated = consolidate_fn(results)

    if feature_flags.ATTACH_PDF_TO_HUBSPOT:
        path = Path("report.pdf")
        path.write_text(json.dumps(consolidated, indent=2))
        try:
            company_id = hubspot_client.upsert(consolidated)
            hubspot_client.attach(str(path), company_id)
        except Exception as e:
            logger.error(f"HubSpot upload failed: {e}")

    return consolidated


def main_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", required=True)
    parser.add_argument("--website", required=True)
    args = parser.parse_args()

    triggers = [
        {
            "source": "cli",
            "creator": "cli@example.com",
            "recipient": "cli@example.com",
            "payload": {"company": args.company, "website": args.website},
        }
    ]

    def researcher_stub(trigger):
        return {"source": "researcher", "payload": trigger["payload"]}

    def consolidate_stub(results):
        return {"company": args.company, "website": args.website}

    class HubspotStub:
        def upsert(self, data):
            logger.info(f"Stub upsert: {data}")
            return "stub-id"

        def attach(self, path, company_id):
            logger.info(f"Stub attach: {path} to {company_id}")

    consolidated = run_pipeline(
        triggers, researcher_stub, consolidate_stub, HubspotStub()
    )
    print(json.dumps(consolidated, indent=2))


if __name__ == "__main__":
    main_cli()
