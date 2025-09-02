#!/usr/bin/env python3
"""Basic runtime check for Google OAuth v2 credentials."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from integrations.google_oauth import build_user_credentials, classify_oauth_error

SCOPES = ["https://www.googleapis.com/auth/userinfo.email"]


def main() -> int:
    creds = build_user_credentials(SCOPES)
    if creds is None:
        print("❌ Missing Google OAuth v2 environment variables")
        return 1
    try:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
    except Exception as exc:  # pragma: no cover - network error conditions
        code, hint = classify_oauth_error(exc)
        print(f"❌ Google OAuth selftest failed ({code}): {hint}")
        return 1
    print("✅ Google OAuth selftest succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
