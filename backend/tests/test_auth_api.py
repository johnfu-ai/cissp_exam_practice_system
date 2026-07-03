import pytest
from fastapi.testclient import TestClient

from app.core.security import InMemoryPasswordResetTokenStore, InMemoryRefreshTokenStore
from app.dependencies import get_lockout_store, get_refresh_store, get_reset_token_store
from app.db.session import get_session
from app.main import create_app
from app.services.auth import InMemoryLockoutStore


@pytest.fixture
def client(db_session, session_with_roles):
    app = create_app()
    refresh_store = InMemoryRefreshTokenStore()
    lockout = InMemoryLockoutStore(threshold=5)
    rst = InMemoryPasswordResetTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: refresh_store
    app.dependency_overrides[get_lockout_store] = lambda: lockout
    app.dependency_overrides[get_reset_token_store] = lambda: rst
    return TestClient(app), refresh_store, lockout, rst


def test_register_and_me(client):
    c, store, _, _ = client
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
    c, store, _, _ = client
    c.post("/api/auth/register", json={"email": "login@example.com", "password": "pw123456"})
    resp = c.post("/api/auth/login", json={"email": "login@example.com", "password": "pw123456"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_wrong_password_then_lockout(client):
    c, store, _, _ = client
    # use a tight-threshold lockout for this test only (single shared instance)
    tight = InMemoryLockoutStore(threshold=2)
    c.app.dependency_overrides[get_lockout_store] = lambda: tight
    c.post("/api/auth/register", json={"email": "lock@example.com", "password": "pw123456"})
    r1 = c.post("/api/auth/login", json={"email": "lock@example.com", "password": "wrong"})
    assert r1.status_code == 401
    r2 = c.post("/api/auth/login", json={"email": "lock@example.com", "password": "wrong"})
    assert r2.status_code == 429


def test_refresh_and_logout(client):
    c, store, _, _ = client
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
    c, _, _, _ = client
    assert c.get("/api/auth/me").status_code == 401


# ---- P0 #1: secure password change + reset ----

def _auth_header(c, email="u@example.com"):
    body = c.post("/api/auth/register",
                  json={"email": email, "password": "pw123456"}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def test_change_password_requires_auth(client):
    c, _, _, _ = client
    r = c.put("/api/auth/password",
              json={"current_password": "x", "new_password": "newpw123"})
    assert r.status_code == 401


def test_change_password_rejects_wrong_current(client):
    c, _, _, _ = client
    h = _auth_header(c)
    r = c.put("/api/auth/password", headers=h,
              json={"current_password": "wrong", "new_password": "newpw123"})
    assert r.status_code == 401


def test_change_password_success_then_login_with_new(client):
    c, _, _, _ = client
    h = _auth_header(c, email="cp@example.com")
    r = c.put("/api/auth/password", headers=h,
              json={"current_password": "pw123456", "new_password": "newpw123"})
    assert r.status_code == 200, r.text
    # old password no longer works
    assert c.post("/api/auth/login",
                  json={"email": "cp@example.com", "password": "pw123456"}).status_code == 401
    # new password works
    assert c.post("/api/auth/login",
                  json={"email": "cp@example.com", "password": "newpw123"}).status_code == 200


def test_reset_request_returns_token_in_dev(client):
    c, _, _, _ = client
    c.post("/api/auth/register", json={"email": "rst@example.com", "password": "pw123456"})
    r = c.post("/api/auth/reset-password/request", json={"email": "rst@example.com"})
    assert r.status_code == 200
    assert r.json().get("token")


def test_reset_request_unknown_email_still_200_no_token(client):
    c, _, _, _ = client
    r = c.post("/api/auth/reset-password/request", json={"email": "nope@example.com"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}  # no token leaked for unknown email


def test_reset_confirm_flow_single_use(client):
    c, _, _, _ = client
    c.post("/api/auth/register", json={"email": "cf@example.com", "password": "pw123456"})
    tok = c.post("/api/auth/reset-password/request",
                 json={"email": "cf@example.com"}).json()["token"]
    r = c.post("/api/auth/reset-password/confirm",
               json={"token": tok, "new_password": "newpw123"})
    assert r.status_code == 200, r.text
    # new password logs in
    assert c.post("/api/auth/login",
                  json={"email": "cf@example.com", "password": "newpw123"}).status_code == 200
    # single-use: same token now invalid
    assert c.post("/api/auth/reset-password/confirm",
                  json={"token": tok, "new_password": "another123"}).status_code == 401


def test_reset_confirm_bogus_token_401(client):
    c, _, _, _ = client
    r = c.post("/api/auth/reset-password/confirm",
               json={"token": "bogus", "new_password": "newpw123"})
    assert r.status_code == 401


def test_old_reset_endpoint_removed(client):
    c, _, _, _ = client
    # the unauthenticated takeover endpoint is gone
    r = c.post("/api/auth/reset-password",
               json={"email": "x@example.com", "new_password": "newpw123"})
    assert r.status_code == 404
