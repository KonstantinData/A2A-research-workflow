"""Unified Google OAuth env handling (v1, v2, JSON)."""
from __future__ import annotations
import os, json
from typing import Optional, List

try:
    from google.oauth2.credentials import Credentials  # type: ignore
except Exception:  # pragma: no cover
    Credentials = None  # type: ignore

DEFAULT_TOKEN_URI = os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token")

def _first(*keys: str) -> Optional[str]:
    for k in keys:
        v = os.getenv(k)
        if v:
            return v
    return None

def _maybe_parse_json_env() -> dict:
    raw = _first("GOOGLE_OAUTH_JSON", "GOOGLE_CREDENTIALS_JSON", "GOOGLE_0")
    if not raw:
        return {}
    try:
        j = json.loads(raw)
        return j.get("installed") or j.get("web") or j
    except Exception:
        return {}

def build_user_credentials(scopes: List[str]) -> Optional["Credentials"]:
    """Return Credentials or None if incomplete/unsupported environment."""
    if Credentials is None:  # libs not installed in test env
        return None

    blob = _maybe_parse_json_env()
    client_id = _first("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_ID_V2") or blob.get("client_id")
    client_secret = _first("GOOGLE_CLIENT_SECRET", "GOOGLE_CLIENT_SECRET_V2") or blob.get("client_secret")
    refresh_token = _first("GOOGLE_REFRESH_TOKEN")
    token_uri = _first("GOOGLE_TOKEN_URI") or blob.get("token_uri") or DEFAULT_TOKEN_URI

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

def which_variant() -> str:
    if os.getenv("GOOGLE_CLIENT_ID_V2") or os.getenv("GOOGLE_CLIENT_SECRET_V2"):
        return "v2"
    if os.getenv("GOOGLE_0") or os.getenv("GOOGLE_OAUTH_JSON") or os.getenv("GOOGLE_CREDENTIALS_JSON"):
        return "json"
    return "v1"
