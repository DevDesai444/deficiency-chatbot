from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_returns_200_and_schema():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"status", "llm", "data_store", "environment"}
    assert body["status"] in ("ok", "degraded")
