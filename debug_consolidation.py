#!/usr/bin/env python3
"""Debug consolidation process."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.consolidate import consolidate
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

print("=== Running all research agents ===")
results = []
for source in SOURCES:
    try:
        result = source(mahle_trigger)
        if result:
            results.append(result)
            print(f"Agent {source.__name__}: {len(result.get('payload', {}))} payload keys")
    except Exception as e:
        print(f"Agent {source.__name__} error: {e}")

print(f"\nTotal results: {len(results)}")

print("\n=== Consolidating results ===")
consolidated = consolidate(results)

print(f"Consolidated keys: {list(consolidated.keys())}")
print(f"Company name: {consolidated.get('company_name')}")
print(f"Domain: {consolidated.get('domain')}")
print(f"Has meta: {bool(consolidated.get('meta'))}")

print("\n=== Testing CSV export format ===")
# Test our export fix
if "rows" in consolidated and "fields" in consolidated:
    print("Already structured format")
    rows = list(consolidated.get("rows") or [])
    fields = list(consolidated.get("fields") or [])
else:
    print("Flat format - converting to rows/fields")
    meta = consolidated.get("meta", {})
    data_row = {k: v for k, v in consolidated.items() if k != "meta"}
    rows = [data_row] if data_row else []
    fields = list(data_row.keys()) if data_row else []

print(f"Rows: {len(rows)}")
print(f"Fields: {fields}")
if rows:
    print(f"First row: {rows[0]}")