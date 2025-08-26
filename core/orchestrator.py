import logging
from integrations.google_calendar import normalize_event
from integrations.email_sender import send_missing_info_reminder

logger = logging.getLogger(__name__)


def gather_triggers(fetch_events, fetch_contacts):
    events = fetch_events()
    contacts = fetch_contacts()

    triggers = []

    for ev in events:
        trig = normalize_event(
            ev,
            detected_trigger="meeting-vorbereitung",  # Beispiel, real: erkenne dynamisch
            creator_email=ev.get("creator"),
            creator_name=ev.get("creator_name"),
        )
        triggers.append(trig)

        # Debug-Log
        logger.info(
            {
                "dbg": "trigger_payload",
                "event_title": trig.get("title"),
                "company": trig.get("company"),
                "start_iso": trig.get("start_iso"),
                "end_iso": trig.get("end_iso"),
            }
        )

    # ggf. Kontakte ebenso verarbeiten…
    return triggers
