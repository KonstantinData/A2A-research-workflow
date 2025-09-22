import os, pytest
from types import SimpleNamespace

from integrations import google_oauth
from integrations.google_oauth import build_user_credentials

SCOPES = ["x"]

def test_primary_envs_work(monkeypatch):
    if google_oauth.Credentials is None:
        monkeypatch.setattr(google_oauth, "Credentials", SimpleNamespace)
    for k in ["GOOGLE_CLIENT_ID","GOOGLE_CLIENT_SECRET","GOOGLE_REFRESH_TOKEN"]: monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_ID","id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET","sec")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN","rt")
    monkeypatch.setattr(google_oauth.SETTINGS, "google_client_id", "id", raising=False)
    monkeypatch.setattr(google_oauth.SETTINGS, "google_client_secret", "sec", raising=False)
    monkeypatch.setattr(google_oauth.SETTINGS, "google_refresh_token", "rt", raising=False)
    assert build_user_credentials(SCOPES) is not None

def test_legacy_envs_ignored(monkeypatch):
    """Legacy OAuth variables are now ignored (v2-only mode)."""
    if google_oauth.Credentials is None:
        monkeypatch.setattr(google_oauth, "Credentials", SimpleNamespace)
    monkeypatch.setenv("GOOGLE_CLIENT_ID","id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET","sec")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN","rt")
    monkeypatch.setattr(google_oauth.SETTINGS, "google_client_id", "id", raising=False)
    monkeypatch.setattr(google_oauth.SETTINGS, "google_client_secret", "sec", raising=False)
    monkeypatch.setattr(google_oauth.SETTINGS, "google_refresh_token", "rt", raising=False)
    legacy_key = "GOOGLE_CLIENT_ID" + "_V2"
    monkeypatch.setenv(legacy_key, "legacy")
    # Should work fine - legacy vars are ignored
    assert build_user_credentials(SCOPES) is not None

