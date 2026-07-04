from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok_with_db_and_redis():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["redis"] == "ok"


def test_live_is_always_200():
    client = TestClient(app)
    response = client.get("/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_happy_path():
    client = TestClient(app)
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["redis"] == "ok"


def test_ready_returns_503_when_dep_down(monkeypatch):
    monkeypatch.setattr("app.main._check_deps", lambda: ("error", "ok"))
    client = TestClient(app)
    response = client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] == "error"


def test_health_returns_503_when_dep_down(monkeypatch):
    # the bug fix: /health no longer always returns 200
    monkeypatch.setattr("app.main._check_deps", lambda: ("error", "error"))
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
