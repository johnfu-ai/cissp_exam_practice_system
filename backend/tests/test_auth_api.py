import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import (
    InMemoryPasswordResetTokenStore,
    InMemoryRateLimiter,
    InMemoryRefreshTokenStore,
    InMemoryRevokedTokenStore,
)
from app.dependencies import (
    get_lockout_store,
    get_rate_limiter,
    get_refresh_store,
    get_reset_token_store,
    get_revoked_store,
)
from app.db.session import get_session
from app.main import create_app
from app.models.auth import User
from app.models.enums import UserStatus
from app.services.auth import InMemoryLockoutStore


@pytest.fixture
def client(db_session, session_with_roles):
    app = create_app()
    refresh_store = InMemoryRefreshTokenStore()
    lockout = InMemoryLockoutStore(threshold=5)
    rst = InMemoryPasswordResetTokenStore()
    revoked = InMemoryRevokedTokenStore()
    rate_limiter = InMemoryRateLimiter()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: refresh_store
    app.dependency_overrides[get_lockout_store] = lambda: lockout
    app.dependency_overrides[get_reset_token_store] = lambda: rst
    app.dependency_overrides[get_revoked_store] = lambda: revoked
    app.dependency_overrides[get_rate_limiter] = lambda: rate_limiter
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


def test_reset_request_returns_token_in_dev_env_variant(client, monkeypatch):
    # APP_ENV=dev (the value used in docker-compose) must also surface the token
    from app.api import auth as auth_api
    monkeypatch.setattr(auth_api.settings, "app_env", "dev")
    c, _, _, _ = client
    c.post("/api/auth/register", json={"email": "devvar@example.com", "password": "pw123456"})
    r = c.post("/api/auth/reset-password/request", json={"email": "devvar@example.com"})
    assert r.status_code == 200
    assert r.json().get("token")


def test_reset_request_no_token_in_production(client, monkeypatch):
    from app.api import auth as auth_api
    monkeypatch.setattr(auth_api.settings, "app_env", "production")
    c, _, _, _ = client
    c.post("/api/auth/register", json={"email": "prodvar@example.com", "password": "pw123456"})
    r = c.post("/api/auth/reset-password/request", json={"email": "prodvar@example.com"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}  # no token leaked in production


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


def test_revoked_access_token_rejected_after_logout(client):
    """#8: logout with the access token revokes its jti, so the token is rejected
    on the next request even though it hasn't reached its natural expiry."""
    c, _, _, _ = client
    reg = c.post("/api/auth/register",
                 json={"email": "rev@example.com", "password": "pw123456"}).json()
    token, refresh = reg["access_token"], reg["refresh_token"]
    h = {"Authorization": f"Bearer {token}"}
    # before logout, the token works
    assert c.get("/api/auth/me", headers=h).status_code == 200
    # logout WITH the access token -> revokes its jti
    out = c.post("/api/auth/logout", json={"refresh_token": refresh, "access_token": token})
    assert out.status_code == 200
    # the same access token is now rejected (revoked, not expired)
    assert c.get("/api/auth/me", headers=h).status_code == 401


def test_disabled_user_token_rejected(client, db_session):
    """#8: a disabled user's existing access token is rejected on the next request
    (status change takes effect immediately, no need to revoke individual tokens)."""
    c, _, _, _ = client
    reg = c.post("/api/auth/register",
                 json={"email": "dis@example.com", "password": "pw123456"}).json()
    token = reg["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert c.get("/api/auth/me", headers=h).status_code == 200
    # disable the user directly in the DB (same effect as the admin endpoint)
    user = db_session.execute(select(User).filter_by(email="dis@example.com")).scalar_one()
    user.status = UserStatus.disabled
    db_session.flush()
    # the same token is now rejected
    assert c.get("/api/auth/me", headers=h).status_code == 401


def test_login_rate_limited_per_ip(client, monkeypatch):
    """#10: per-IP rate limiting on login — after the limit, further logins from
    the same IP get 429 (caps credential-stuffing)."""
    from app.core.config import settings as _settings

    c, _, _, _ = client
    monkeypatch.setattr(_settings, "login_rate_limit", 2)
    monkeypatch.setattr(_settings, "login_rate_window_seconds", 60)
    rl = InMemoryRateLimiter()  # one shared instance so the counter accumulates
    c.app.dependency_overrides[get_rate_limiter] = lambda: rl
    c.post("/api/auth/register", json={"email": "rl@example.com", "password": "pw123456"})
    assert c.post("/api/auth/login", json={"email": "rl@example.com", "password": "pw123456"}).status_code == 200
    # second login (wrong password) is still allowed by the rate limiter (401 from auth)
    assert c.post("/api/auth/login", json={"email": "rl@example.com", "password": "wrong"}).status_code == 401
    # third login is rate-limited
    assert c.post("/api/auth/login", json={"email": "rl@example.com", "password": "pw123456"}).status_code == 429
