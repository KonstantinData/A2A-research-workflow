import os
from integrations.google_oauth import build_user_credentials, classify_oauth_error

SCOPES = ["x"]


def _clear():
    for k in list(os.environ.keys()):
        if k.startswith("GOOGLE_"):
            os.environ.pop(k, None)


def test_v1_names_rejected(monkeypatch):
    _clear()
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "rt")
    assert build_user_credentials(SCOPES) is None


def test_v2_names_work(monkeypatch):
    _clear()
    monkeypatch.setenv("GOOGLE_CLIENT_ID_V2", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET_V2", "sec")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "rt")
    assert build_user_credentials(SCOPES) is not None


def test_invalid_grant_hint():
    code, hint = classify_oauth_error(Exception("invalid_grant: expired"))
    assert code == "invalid_grant"
    assert "Refresh token" in hint

