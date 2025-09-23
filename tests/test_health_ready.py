from fastapi.testclient import TestClient

from api.workflow_api import app


client = TestClient(app)


def test_healthz_returns_ok() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_readyz_returns_ready() -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"ready": True}


def test_readyz_returns_unavailable_when_event_store_fails(monkeypatch) -> None:
    def _raise(**_kwargs: object) -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr("api.workflow_api.list_events", _raise)

    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json() == {"detail": "Event store unavailable"}
