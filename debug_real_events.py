#!/usr/bin/env python3
"""Debug script to test trigger detection with real calendar events"""

from integrations.google_calendar import fetch_events
from core.trigger_words import contains_trigger, normalize_text
from core.triggers import gather_calendar_triggers

print("=== Fetching Real Calendar Events ===")
events = fetch_events()
print(f"Found {len(events)} events")

print("\n=== Testing Trigger Detection on Real Events ===")
for i, event in enumerate(events):
    payload = event.get("payload", event)
    summary = payload.get("summary", "")
    description = payload.get("description", "")
    
    # Test trigger detection
    trigger_result = contains_trigger(payload)
    
    print(f"\n{i+1}. Event ID: {payload.get('event_id', 'No ID')}")
    print(f"   Summary: '{summary}'")
    if description:
        print(f"   Description: '{description[:100]}...'")
    print(f"   Normalized: '{normalize_text(summary)}'")
    print(f"   Trigger Match: {trigger_result}")
    
    # Check specific trigger words
    norm_summary = normalize_text(summary)
    if "customer" in norm_summary and "meeting" in norm_summary:
        print(f"   ✓ Contains 'customer' and 'meeting'")
    if "customer-meeting" in norm_summary:
        print(f"   ✓ Contains 'customer-meeting'")

print("\n=== Testing gather_calendar_triggers ===")
logged_events = []
logged_steps = []

def fake_log_event(entry):
    logged_events.append(entry)

def fake_log_step(source, stage, data, severity="info"):
    logged_steps.append((source, stage, data, severity))

def fake_get_workflow_id():
    return "debug-real-workflow"

result_triggers = gather_calendar_triggers(
    events=events,
    fetch_events=None,
    calendar_fetch_logged=lambda wf_id: None,
    calendar_last_error=lambda wf_id: None,
    get_workflow_id=fake_get_workflow_id,
    log_event=fake_log_event,
    log_step=fake_log_step,
    contains_trigger=contains_trigger
)

print(f"\n=== Final Results ===")
print(f"Found {len(result_triggers)} triggers out of {len(events)} events")
for i, trigger in enumerate(result_triggers):
    payload = trigger.get("payload", {})
    print(f"{i+1}. {payload.get('summary', 'No summary')}")

print(f"\nDiscarded events:")
for event in logged_events:
    if event.get("status") == "not_relevant":
        print(f"- Event ID: {event.get('event_id')}")

for step in logged_steps:
    if step[1] == "event_discarded":
        event_info = step[2].get("event", {})
        print(f"- '{event_info.get('summary', 'No summary')}' (reason: {step[2].get('reason')})")