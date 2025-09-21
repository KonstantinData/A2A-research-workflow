"""Google OAuth: requires GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN."""
from __future__ import annotations

from typing import Optional, List, Tuple

import time

import requests

from config.settings import SETTINGS
from core.utils import log_step
from app.core.policy.retry import MAX_ATTEMPTS, backoff_seconds

try:
    from google.oauth2.credentials import Credentials  # type: ignore
except Exception:
    Credentials = None  # type: ignore

DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"


class OAuthError(Exception):
    """Raised when refreshing an OAuth token fails."""


def build_user_credentials(scopes: List[str]) -> Optional["Credentials"]:
    if Credentials is None:
        return None
    client_id = SETTINGS.google_client_id
    client_secret = SETTINGS.google_client_secret
    refresh_token = SETTINGS.google_refresh_token
    token_uri = SETTINGS.google_token_uri or DEFAULT_TOKEN_URI
    if not (client_id and client_secret and refresh_token):
        log_step("google_oauth", "credentials_missing", 
                {"client_id_set": bool(client_id), "client_secret_set": bool(client_secret), 
                 "refresh_token_set": bool(refresh_token)}, severity="info")
        return None
    # Legacy OAuth check removed - using v2-only configuration
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
        "client_id": getattr(SETTINGS, "google_client_id", ""),
        "client_secret": getattr(SETTINGS, "google_client_secret", ""),
        "refresh_token": getattr(SETTINGS, "google_refresh_token", ""),
        "grant_type": "refresh_token",
    }
    token_uri = getattr(SETTINGS, "google_token_uri", DEFAULT_TOKEN_URI)
    response = None
    last_exc: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.post(token_uri, data=payload, timeout=30)
        except requests.RequestException as exc:
            last_exc = exc
            if attempt >= MAX_ATTEMPTS:
                log_step(
                    "oauth",
                    "google_token_request_failed",
                    {"error": str(exc), "attempt": attempt},
                    severity="error",
                )
                raise
            delay = backoff_seconds(attempt)
            log_step(
                "oauth",
                "google_token_retry",
                {
                    "attempt": attempt,
                    "error": str(exc),
                    "backoff_seconds": round(delay, 2),
                },
                severity="warning",
            )
            time.sleep(delay)
            continue
        if response.status_code >= 500:
            if attempt >= MAX_ATTEMPTS:
                log_step(
                    "oauth",
                    "google_token_request_failed",
                    {
                        "status": response.status_code,
                        "attempt": attempt,
                        "error": response.text[:200],
                    },
                    severity="error",
                )
                response.raise_for_status()
            else:
                delay = backoff_seconds(attempt)
                log_step(
                    "oauth",
                    "google_token_retry",
                    {
                        "attempt": attempt,
                        "status": response.status_code,
                        "backoff_seconds": round(delay, 2),
                    },
                    severity="warning",
                )
                time.sleep(delay)
                continue
        break
    if response is None:
        if last_exc:
            raise last_exc
        raise OAuthError("Failed to refresh Google token")
    r = response
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
