#!/usr/bin/env python3
"""Debug script to test Google Calendar fetching"""

import os
from integrations.google_calendar import fetch_events
from config.settings import SETTINGS

print("=== Google Calendar Configuration ===")
print(f"GOOGLE_CLIENT_ID: {os.getenv('GOOGLE_CLIENT_ID', 'Not set')[:20]}...")
print(f"GOOGLE_CLIENT_SECRET: {'Set' if os.getenv('GOOGLE_CLIENT_SECRET') else 'Not set'}")
print(f"GOOGLE_REFRESH_TOKEN: {'Set' if os.getenv('GOOGLE_REFRESH_TOKEN') else 'Not set'}")
print(f"GOOGLE_CALENDAR_IDS: {os.getenv('GOOGLE_CALENDAR_IDS', 'Not set')}")
print(f"SETTINGS.google_calendar_ids: {SETTINGS.google_calendar_ids}")
print(f"CAL_LOOKBACK_DAYS: {SETTINGS.cal_lookback_days}")
print(f"CAL_LOOKAHEAD_DAYS: {SETTINGS.cal_lookahead_days}")
print(f"LIVE_MODE: {os.getenv('LIVE_MODE', '1')}")

print("\n=== Attempting to Fetch Events ===")
try:
    events = fetch_events()
    print(f"Successfully fetched {len(events)} events")
    
    if events:
        print("\n=== Event Details ===")
        for i, event in enumerate(events[:5]):  # Show first 5 events
            payload = event.get("payload", event)
            summary = payload.get("summary", "No summary")
            description = payload.get("description", "")
            event_id = payload.get("event_id", "No ID")
            print(f"{i+1}. ID: {event_id}")
            print(f"   Summary: {summary}")
            if description:
                print(f"   Description: {description[:100]}...")
            print()
        
        if len(events) > 5:
            print(f"... and {len(events) - 5} more events")
    else:
        print("No events found in the specified time window")
        
except Exception as e:
    print(f"Error fetching events: {e}")
    print(f"Error type: {type(e).__name__}")
    
    # Check if it's a missing dependencies issue
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        print("Google API libraries are available")
    except ImportError as ie:
        print(f"Missing Google API libraries: {ie}")