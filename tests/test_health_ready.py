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
