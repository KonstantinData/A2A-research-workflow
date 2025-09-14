import pytest
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import core.orchestrator as orch

def test_live_guard_fails_without_env(monkeypatch):
    monkeypatch.setenv("LIVE_MODE","1")
    for k in [
        "GOOGLE_CLIENT_ID_V2",
        "GOOGLE_CLIENT_SECRET_V2",
        "GOOGLE_REFRESH_TOKEN",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASS",
        "SMTP_FROM",
        "MAIL_FROM",
        "HUBSPOT_ACCESS_TOKEN",
    ]:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(Exception):
        orch._assert_live_ready()
