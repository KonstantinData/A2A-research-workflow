#!/usr/bin/env python3
"""Debug script to test the full trigger detection flow"""

import os
from core.trigger_words import contains_trigger, load_trigger_words
from core.triggers import gather_calendar_triggers, _as_trigger_from_event
from integrations.google_calendar import fetch_events

print("=== Environment Check ===")
print(f"GOOGLE_CALENDAR_IDS: {os.getenv('GOOGLE_CALENDAR_IDS')}")
print(f"LIVE_MODE: {os.getenv('LIVE_MODE', '1')}")
print(f"TRIGGER_WORDS_FILE: {os.getenv('TRIGGER_WORDS_FILE', 'config/trigger_words.txt')}")

print("\n=== Trigger Words ===")
triggers = load_trigger_words()
print(f"Loaded {len(triggers)} trigger words")
print("First 10:", triggers[:10])

print("\n=== Test Event Processing ===")
# Create test events that should trigger
test_events = [
    {
        "event_id": "test1",
        "summary": "Research meeting with ABC Corp",
        "description": "",
        "creator": {"email": "alice@example.com"},
        "organizer": {"email": "bob@example.com"},
        "payload": {
            "event_id": "test1",
            "summary": "Research meeting with ABC Corp",
            "description": "",
            "creator": {"email": "alice@example.com"},
            "organizer": {"email": "bob@example.com"},
        }
    },
    {
        "event_id": "test2", 
        "summary": "Regular team meeting",
        "description": "",
        "creator": {"email": "alice@example.com"},
        "organizer": {"email": "bob@example.com"},
        "payload": {
            "event_id": "test2",
            "summary": "Regular team meeting", 
            "description": "",
            "creator": {"email": "alice@example.com"},
            "organizer": {"email": "bob@example.com"},
        }
    }
]

print("\n=== Direct Trigger Detection ===")
for event in test_events:
    payload = event.get("payload", event)
    result = contains_trigger(payload)
    print(f"Event '{payload.get('summary')}' -> {result}")

print("\n=== _as_trigger_from_event Test ===")
for event in test_events:
    trigger = _as_trigger_from_event(event, contains_trigger=contains_trigger)
    summary = event.get("payload", event).get("summary", "")
    print(f"Event '{summary}' -> {'TRIGGER' if trigger else 'NO TRIGGER'}")

print("\n=== gather_calendar_triggers Test ===")
logged_events = []
logged_steps = []

def fake_log_event(entry):
    logged_events.append(entry)
    print(f"LOG EVENT: {entry}")

def fake_log_step(source, stage, data, severity="info"):
    logged_steps.append((source, stage, data, severity))
    print(f"LOG STEP: {source}.{stage} -> {data} [{severity}]")

def fake_get_workflow_id():
    return "debug-workflow"

result_triggers = gather_calendar_triggers(
    events=test_events,
    fetch_events=None,  # Don't fetch, use provided events
    calendar_fetch_logged=lambda wf_id: None,
    calendar_last_error=lambda wf_id: None,
    get_workflow_id=fake_get_workflow_id,
    log_event=fake_log_event,
    log_step=fake_log_step,
    contains_trigger=contains_trigger
)

print(f"\n=== Results ===")
print(f"Found {len(result_triggers)} triggers")
for i, trigger in enumerate(result_triggers):
    payload = trigger.get("payload", {})
    print(f"{i+1}. {payload.get('summary', 'No summary')} (source: {trigger.get('source')})")

print(f"\nLogged {len(logged_events)} events and {len(logged_steps)} steps")