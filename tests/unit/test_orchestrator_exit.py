import pytest

from core import orchestrator


def test_main_handles_string_exit(monkeypatch):
    def fake_run():
        raise SystemExit("No real calendar events detected – aborting run")

    monkeypatch.setattr(orchestrator, "run", fake_run)
    monkeypatch.setattr(orchestrator, "build_user_credentials", lambda scopes: object())
    rc = orchestrator.main([])
    assert rc == 0
