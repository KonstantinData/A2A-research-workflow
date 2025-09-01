import os, importlib, pytest

def test_live_guard_fails_without_env(monkeypatch):
    monkeypatch.setenv("LIVE_MODE","1")
    for k in ["GOOGLE_CLIENT_ID","GOOGLE_CLIENT_SECRET","GOOGLE_REFRESH_TOKEN","SMTP_HOST","SMTP_PORT","MAIL_FROM","HUBSPOT_ACCESS_TOKEN"]:
        monkeypatch.delenv(k, raising=False)
    orch = importlib.import_module("core.orchestrator")
    with pytest.raises(Exception):
        orch._assert_live_ready()
