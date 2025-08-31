import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations.google_oauth import build_user_credentials

SCOPES = ["x"]

def _clear(keys):
    for k in keys:
        os.environ.pop(k, None)

def test_v2_names_work(monkeypatch):
    _clear([
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REFRESH_TOKEN",
        "GOOGLE_CLIENT_ID_V2",
        "GOOGLE_CLIENT_SECRET_V2",
    ])
    monkeypatch.setenv("GOOGLE_CLIENT_ID_V2", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET_V2", "sec")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "rt")
    assert build_user_credentials(SCOPES) is not None

def test_v1_names_work(monkeypatch):
    _clear([
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REFRESH_TOKEN",
        "GOOGLE_CLIENT_ID_V2",
        "GOOGLE_CLIENT_SECRET_V2",
    ])
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "rt")
    assert build_user_credentials(SCOPES) is not None
