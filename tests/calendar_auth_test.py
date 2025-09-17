# tests/calendar_auth_test.py

import os
import pytest
from dotenv import load_dotenv

# Only import Google libs if we actually run live checks
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request

    _GOOGLE_LIBS_OK = True
except Exception:
    _GOOGLE_LIBS_OK = False

# Load .env if present (local runs)
load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
]

REQUIRED = [
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REFRESH_TOKEN",
    "GOOGLE_TOKEN_URI",
]

missing = [k for k in REQUIRED if not os.getenv(k)]
if missing:
    pytest.skip(
        f"Skipping calendar auth test due to missing env: {', '.join(missing)}",
        allow_module_level=True,
    )


def test_required_env_present_and_sane():
    for key in REQUIRED:
        val = os.getenv(key)
        assert isinstance(val, str) and val.strip(), f"{key} is missing or empty"
    uri = os.getenv("GOOGLE_TOKEN_URI", "")
    assert uri.startswith(
        ("http://", "https://")
    ), "GOOGLE_TOKEN_URI must start with http/https"
    assert any(
        token in uri.lower() for token in ("oauth", "token")
    ), "GOOGLE_TOKEN_URI should contain oauth/token"


@pytest.mark.live
def test_refresh_and_list_calendars_when_enabled():
    """
    Runs a real refresh + Calendar API call only when explicitly enabled.
    Set RUN_LIVE_GOOGLE_TESTS=1 to execute; otherwise the test is skipped.
    """
    if os.getenv("RUN_LIVE_GOOGLE_TESTS", "0") != "1":
        pytest.skip("Set RUN_LIVE_GOOGLE_TESTS=1 to run live Google API checks")
    if not _GOOGLE_LIBS_OK:
        pytest.skip("Google client libraries not available in this environment")

    creds = Credentials(
        None,
        refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        token_uri=os.getenv("GOOGLE_TOKEN_URI"),
        scopes=SCOPES,
    )

    # Refresh access token
    creds.refresh(Request())
    assert creds.valid or creds.token, "Credentials should be valid after refresh"

    # Basic sanity: list calendars
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    calendars = service.calendarList().list(maxResults=1).execute()
    assert "items" in calendars and isinstance(calendars["items"], list)
