#!/usr/bin/env python3
"""Google OAuth self-test for v2 client.

This script verifies that the configured GOOGLE_CLIENT_ID_V2,
GOOGLE_CLIENT_SECRET_V2 and GOOGLE_REFRESH_TOKEN are valid by attempting
an OAuth token refresh against the Google token endpoint.
"""

import os
import sys
import requests

CID = os.getenv("GOOGLE_CLIENT_ID_V2")
CSEC = os.getenv("GOOGLE_CLIENT_SECRET_V2")
RTOK = os.getenv("GOOGLE_REFRESH_TOKEN")
TURI = os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token")


def fail(msg: str) -> None:
    """Exit the script with a message."""
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    """Run the self test."""
    if not all([CID, CSEC, RTOK]):
        fail(
            "Missing v2 envs: GOOGLE_CLIENT_ID_V2 / GOOGLE_CLIENT_SECRET_V2 / GOOGLE_REFRESH_TOKEN"
        )

    data = {
        "client_id": CID,
        "client_secret": CSEC,
        "refresh_token": RTOK,
        "grant_type": "refresh_token",
    }
    try:
        resp = requests.post(TURI, data=data, timeout=10)
    except Exception as exc:  # network / request errors
        fail(str(exc))
    if resp.status_code != 200:
        try:
            msg = resp.json().get("error", resp.text)
        except Exception:
            msg = resp.text
        hint = ""
        err = msg.lower()
        if "invalid_grant" in err:
            hint = (
                "invalid_grant: refresh token expired/revoked or not issued for this v2 client."
            )
        elif "invalid_client" in err:
            hint = "invalid_client: verify GOOGLE_CLIENT_ID_V2 / GOOGLE_CLIENT_SECRET_V2."
        fail(f"{msg}. {hint}")
    print("OK")


if __name__ == "__main__":
    main()
