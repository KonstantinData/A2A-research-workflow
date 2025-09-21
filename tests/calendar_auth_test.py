# tests/calendar_auth_test.py

import pytest
from dotenv import load_dotenv

from config.settings import Settings

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

]

SETTINGS_OBJ = Settings()

REQUIRED = {
    "GOOGLE_CLIENT_ID": SETTINGS_OBJ.google_client_id,
    "GOOGLE_CLIENT_SECRET": SETTINGS_OBJ.google_client_secret,
    "GOOGLE_REFRESH_TOKEN": SETTINGS_OBJ.google_refresh_token,
    "GOOGLE_TOKEN_URI": SETTINGS_OBJ.google_token_uri,
}

missing = [name for name, value in REQUIRED.items() if not (value or "").strip()]
if missing:
    pytest.skip(
        f"Skipping calendar auth test due to missing env: {', '.join(missing)}",
        allow_module_level=True,
    )


def test_required_env_present_and_sane():
    for key, value in REQUIRED.items():
        assert isinstance(value, str) and value.strip(), f"{key} is missing or empty"
    uri = SETTINGS_OBJ.google_token_uri or ""
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
    if not SETTINGS_OBJ.run_live_google_tests:
        pytest.skip("Set RUN_LIVE_GOOGLE_TESTS=1 to run live Google API checks")
    if not _GOOGLE_LIBS_OK:
        pytest.skip("Google client libraries not available in this environment")

    creds = Credentials(
        None,
        refresh_token=SETTINGS_OBJ.google_refresh_token,
        client_id=SETTINGS_OBJ.google_client_id,
        client_secret=SETTINGS_OBJ.google_client_secret,
        token_uri=SETTINGS_OBJ.google_token_uri,
        scopes=SCOPES,
    )

    # Refresh access token
    creds.refresh(Request())
    assert creds.valid or creds.token, "Credentials should be valid after refresh"

    # Basic sanity: list calendars
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    calendars = service.calendarList().list(maxResults=1).execute()
    assert "items" in calendars and isinstance(calendars["items"], list)
