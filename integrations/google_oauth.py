"""Centralized Google OAuth handling for v1/v2/JSON envs with helpful error mapping."""
from __future__ import annotations
import os, json
from typing import Optional, List, Tuple

try:
    from google.oauth2.credentials import Credentials  # type: ignore
except Exception:  # pragma: no cover
    Credentials = None  # type: ignore

DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"


def _env_first(*keys: str) -> Optional[str]:
    for k in keys:
        v = os.getenv(k)
        if v:
            return v
    return None


def _json_blob() -> dict:
    raw = _env_first("GOOGLE_OAUTH_JSON", "GOOGLE_CREDENTIALS_JSON", "GOOGLE_0")
    if not raw:
        return {}
    try:
        j = json.loads(raw)
        return j.get("installed") or j.get("web") or j
    except Exception:
        return {}


def which_variant() -> str:
    if os.getenv("GOOGLE_CLIENT_ID_V2") or os.getenv("GOOGLE_CLIENT_SECRET_V2"):
        return "v2"
    if os.getenv("GOOGLE_0") or os.getenv("GOOGLE_OAUTH_JSON") or os.getenv("GOOGLE_CREDENTIALS_JSON"):
        return "json"
    return "v1"


def build_user_credentials(scopes: List[str]) -> Optional["Credentials"]:
    """Build Credentials from v1 or v2 env names, or a JSON blob. Returns None if incomplete."""
    if Credentials is None:
        return None

    blob = _json_blob()
    client_id = _env_first("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_ID_V2") or blob.get("client_id")
    client_secret = _env_first("GOOGLE_CLIENT_SECRET", "GOOGLE_CLIENT_SECRET_V2") or blob.get("client_secret")
    refresh_token = _env_first("GOOGLE_REFRESH_TOKEN") or blob.get("refresh_token")
    token_uri = _env_first("GOOGLE_TOKEN_URI") or blob.get("token_uri") or DEFAULT_TOKEN_URI

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
    """Return (code, human_hint)."""
    msg = str(err).lower()
    if "invalid_grant" in msg:
        return (
            "invalid_grant",
            "Refresh token is expired/revoked OR does not belong to this client. "
            "Re-issue consent using the SAME client (access_type=offline, prompt=consent).",
        )
    if "invalid_client" in msg:
        return ("invalid_client", "Client ID/secret mismatch; check env and GitHub secrets mapping.")
    if "unauthorized_client" in msg:
        return ("unauthorized_client", "Client not allowed for this flow/scope in Cloud Console.")
    if "invalid_scope" in msg:
        return ("invalid_scope", "Requested scopes not enabled/approved; check Calendar/People scopes.")
    return ("unknown_oauth_error", "See full exception in logs; enable verbose logging if needed.")

