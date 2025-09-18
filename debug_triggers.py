#!/usr/bin/env python3
"""Debug script to test trigger detection"""

from core.trigger_words import contains_trigger, load_trigger_words, normalize_text

# Test event data
test_events = [
    {"summary": "Research meeting with ABC Corp", "description": ""},
    {"summary": "Meeting preparation for XYZ Ltd", "description": ""},
    {"summary": "Besuchsvorbereitung call", "description": ""},
    {"summary": "Customer research session", "description": ""},
    {"summary": "Regular team meeting", "description": ""},
    {"summary": "Kundenrecherche für Firma ABC", "description": ""},
]

print("=== Loaded Trigger Words ===")
triggers = load_trigger_words()
print(f"Total triggers loaded: {len(triggers)}")
for i, trigger in enumerate(triggers[:10]):  # Show first 10
    print(f"{i+1:2d}. {trigger}")
if len(triggers) > 10:
    print(f"... and {len(triggers) - 10} more")

print("\n=== Testing Event Trigger Detection ===")
for i, event in enumerate(test_events, 1):
    result = contains_trigger(event)
    summary = event.get("summary", "")
    normalized = normalize_text(summary)
    print(f"{i}. '{summary}' -> {result}")
    print(f"   Normalized: '{normalized}'")
    
    # Manual check for debugging
    for trigger in triggers[:5]:  # Check first few triggers
        norm_trigger = normalize_text(trigger)
        if norm_trigger in normalized:
            print(f"   ✓ Matches trigger: '{trigger}' (normalized: '{norm_trigger}')")
            break
    print()