import os, pytest
from integrations.google_oauth import build_user_credentials

SCOPES = ["x"]

def test_google_envs_work(monkeypatch):
    for k in [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REFRESH_TOKEN",
        "GOOGLE_OAUTH_JSON",
        "GOOGLE_CREDENTIALS_JSON",
    ]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "rt")
    assert build_user_credentials(SCOPES) is not None

def test_legacy_envs_cause_error(monkeypatch):
    for k in [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REFRESH_TOKEN",
        "GOOGLE_OAUTH_JSON",
        "GOOGLE_CREDENTIALS_JSON",
    ]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "rt")
    legacy_key = "GOOGLE_" + "OAUTH_JSON"
    monkeypatch.setenv(legacy_key, "legacy")
    with pytest.raises(RuntimeError):
        build_user_credentials(SCOPES)

