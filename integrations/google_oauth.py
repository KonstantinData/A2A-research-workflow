"""Google OAuth: requires GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN."""
from __future__ import annotations

import os
from typing import Optional, List, Tuple

import requests

from config.settings import SETTINGS
from core.utils import log_step

try:
    from google.oauth2.credentials import Credentials  # type: ignore
except Exception:
    Credentials = None  # type: ignore

DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"


def _get_env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value:
        return value
    if name in {"GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"}:
        legacy = os.getenv(f"{name}_V2")
        if legacy:
            return legacy
    return None


class OAuthError(Exception):
    """Raised when refreshing an OAuth token fails."""


def build_user_credentials(scopes: List[str]) -> Optional["Credentials"]:
    if Credentials is None:
        return None
    client_id = _get_env("GOOGLE_CLIENT_ID")
    client_secret = _get_env("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    token_uri = os.getenv("GOOGLE_TOKEN_URI") or DEFAULT_TOKEN_URI
    if not (client_id and client_secret and refresh_token):
        return None
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri=token_uri,
        scopes=scopes or None,
    )

def classify_oauth_error(err: Exception) -> Tuple[str, str]:
    msg = str(err).lower()
    if "invalid_grant" in msg:
        return ("invalid_grant",
                "Refresh token expired/revoked or not issued for this client. "
                "Ensure Consent Screen is IN PRODUCTION and re-issue with the same client "
                "(access_type=offline, prompt=consent).")
    if "invalid_client" in msg:
        return ("invalid_client", "Check GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET values.")
    if "unauthorized_client" in msg:
        return ("unauthorized_client", "Client not allowed for scopes; verify Cloud Console settings.")
    if "invalid_scope" in msg:
        return ("invalid_scope", "Enable Calendar/People scopes on the consent screen.")
    return ("unknown_oauth_error", "See full exception in logs.")


def refresh_access_token() -> str:
    payload = {
        "client_id": _get_env("GOOGLE_CLIENT_ID")
        or getattr(SETTINGS, "google_client_id", ""),
        "client_secret": _get_env("GOOGLE_CLIENT_SECRET")
        or getattr(SETTINGS, "google_client_secret", ""),
        "refresh_token": os.getenv("GOOGLE_REFRESH_TOKEN")
        or getattr(SETTINGS, "google_refresh_token", ""),
        "grant_type": "refresh_token",
    }
    token_uri = os.getenv("GOOGLE_TOKEN_URI") or getattr(
        SETTINGS, "google_token_uri", DEFAULT_TOKEN_URI
    )
    r = requests.post(token_uri, data=payload, timeout=30)
    if r.status_code == 400 and "invalid_grant" in r.text:
        log_step(
            "oauth", "google_invalid_grant", {"message": r.text}, severity="error"
        )
        try:
            from integrations.email_sender import send_email

            send_email(
                to="admin@yourdomain.com",
                subject="[A2A] Google OAuth invalid_grant – action required",
                body=f"Refresh token is invalid/expired.\nResponse: {r.text}",
            )
        except Exception:
            pass
        raise OAuthError("Google refresh token invalid_grant")
    r.raise_for_status()
    token = r.json().get("access_token", "")
    if not token:
        raise OAuthError("No access_token in response")
    log_step("oauth", "google_token_refreshed", {}, severity="info")
    return token
