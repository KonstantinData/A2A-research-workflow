#!/usr/bin/env python3
import os, sys
bad = [k for k in ["GOOGLE_CLIENT_ID","GOOGLE_CLIENT_SECRET","GOOGLE_0","GOOGLE_OAUTH_JSON","GOOGLE_CREDENTIALS_JSON"] if os.getenv(k)]
if bad:
    print("❌ Legacy Google OAuth env present:", ", ".join(bad))
    sys.exit(1)
print("✅ v2-only env check passed.")
