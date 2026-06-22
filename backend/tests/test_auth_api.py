import pytest
from fastapi.testclient import TestClient

from app.core.security import InMemoryRefreshTokenStore
from app.dependencies import get_lockout_store, get_refresh_store
from app.db.session import get_session
from app.main import create_app
from app.services.auth import InMemoryLockoutStore


@pytest.fixture
def client(db_session, session_with_roles):
    app = create_app()
    refresh_store = InMemoryRefreshTokenStore()
    lockout = InMemoryLockoutStore(threshold=2)
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: refresh_store
    app.dependency_overrides[get_lockout_store] = lambda: lockout
    return TestClient(app), refresh_store, lockout


def test_register_and_me(client):
    c, store, _ = client
    resp = c.post("/api/auth/register",
                  json={"email": "API@Example.com", "password": "pw123456", "display_name": "API"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["email"] == "api@example.com"
    assert body["access_token"] and body["refresh_token"]
    me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "api@example.com"


def test_login_success(client):
    c, store, _ = client
    c.post("/api/auth/register", json={"email": "login@example.com", "password": "pw123456"})
    resp = c.post("/api/auth/login", json={"email": "login@example.com", "password": "pw123456"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_wrong_password_then_lockout(client):
    c, store, _ = client
    c.post("/api/auth/register", json={"email": "lock@example.com", "password": "pw123456"})
    r1 = c.post("/api/auth/login", json={"email": "lock@example.com", "password": "wrong"})
    assert r1.status_code == 401
    r2 = c.post("/api/auth/login", json={"email": "lock@example.com", "password": "wrong"})
    assert r2.status_code == 429


def test_refresh_and_logout(client):
    c, store, _ = client
    reg = c.post("/api/auth/register", json={"email": "r@example.com", "password": "pw123456"}).json()
    rt = reg["refresh_token"]
    resp = c.post("/api/auth/refresh", json={"refresh_token": rt})
    assert resp.status_code == 200
    new_rt = resp.json()["refresh_token"]
    assert new_rt != rt
    # old refresh rotated away
    assert c.post("/api/auth/refresh", json={"refresh_token": rt}).status_code == 401
    out = c.post("/api/auth/logout", json={"refresh_token": new_rt})
    assert out.status_code == 200
    assert c.post("/api/auth/refresh", json={"refresh_token": new_rt}).status_code == 401


def test_me_without_token_401(client):
    c, _, _ = client
    assert c.get("/api/auth/me").status_code == 401


def test_reset_password(client):
    c, _, _ = client
    c.post("/api/auth/register", json={"email": "reset@example.com", "password": "pw123456"})
    resp = c.post("/api/auth/reset-password",
                  json={"email": "reset@example.com", "new_password": "newpw123"})
    assert resp.status_code == 200
    # can login with new password
    login = c.post("/api/auth/login", json={"email": "reset@example.com", "password": "newpw123"})
    assert login.status_code == 200
