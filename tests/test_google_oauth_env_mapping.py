import os, pytest
from integrations.google_oauth import build_user_credentials

SCOPES = ["x"]

def test_v2_envs_work(monkeypatch):
    for k in ["GOOGLE_CLIENT_ID_V2","GOOGLE_CLIENT_SECRET_V2","GOOGLE_REFRESH_TOKEN"]: monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_ID_V2","id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET_V2","sec")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN","rt")
    assert build_user_credentials(SCOPES) is not None

def test_legacy_envs_cause_error(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID_V2","id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET_V2","sec")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN","rt")
    legacy_key = "GOOGLE_" + "CLIENT_ID"
    monkeypatch.setenv(legacy_key, "legacy")
    with pytest.raises(RuntimeError):
        build_user_credentials(SCOPES)

