#!/usr/bin/env python3
"""Debug script to test research agents with Mahle data."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from agents import agent_internal_search
from core.sources_registry import SOURCES

# Simulate Mahle trigger
mahle_trigger = {
    "source": "calendar",
    "creator": "info@condata.io",
    "recipient": "info@condata.io",
    "payload": {
        "event_id": "7ht8dotjn8ebrkn7kbvfc9mqv4",
        "company_name": "Mahle",
        "domain": "mahle.com",
        "summary": "Meeting with Mahle",
        "description": "Research meeting with Mahle company",
        "creatorEmail": "info@condata.io"
    }
}

print("=== Testing Mahle Trigger ===")
print(f"Trigger: {mahle_trigger}")
print()

print("=== Testing agent_internal_search ===")
try:
    result = agent_internal_search.run(mahle_trigger)
    print(f"Result: {result}")
    print(f"Has payload: {bool(result.get('payload'))}")
    if result.get('payload'):
        print(f"Payload keys: {list(result['payload'].keys())}")
except Exception as e:
    print(f"Error: {e}")
print()

print("=== Testing all SOURCES ===")
for i, source in enumerate(SOURCES):
    print(f"{i+1}. {source.__module__}.{source.__name__}")
    try:
        result = source(mahle_trigger)
        print(f"   Result: {result}")
        if result and result.get('payload'):
            print(f"   Payload keys: {list(result['payload'].keys())}")
    except Exception as e:
        print(f"   Error: {e}")
    print()