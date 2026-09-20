from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_is_liveness_only():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_returns_dependency_status(monkeypatch):
    monkeypatch.setattr(
        "app.main.readiness_status",
        lambda: (True, {"postgresql": "ok", "redis": "ok", "minio": "ok"}),
    )
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["components"]["minio"] == "ok"


def test_ready_returns_503_when_a_dependency_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        "app.main.readiness_status",
        lambda: (
            False,
            {"postgresql": "ok", "redis": "unavailable", "minio": "ok"},
        ),
    )
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
