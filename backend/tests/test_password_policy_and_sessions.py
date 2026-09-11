"""Password policy + session invalidation + mailer wiring tests."""

import pytest
from fastapi.testclient import TestClient

from app.core.password_policy import validate_password
from app.core.security import (
    InMemoryPasswordResetTokenStore,
    InMemoryRateLimiter,
    InMemoryRefreshTokenStore,
    InMemoryRevokedTokenStore,
)
from app.db.session import get_session
from app.dependencies import (
    get_lockout_store,
    get_mailer,
    get_rate_limiter,
    get_refresh_store,
    get_reset_token_store,
    get_revoked_store,
)
from app.main import create_app
from app.services.auth import (
    InMemoryLockoutStore,
    confirm_password_reset,
    register_user,
    request_password_reset,
)


def test_password_policy_accepts_strong():
    assert validate_password("GoodPass12") == "GoodPass12"


@pytest.mark.parametrize("pw", ["short1A", "nodigitsABCdef", "1234567890", "password123"])
def test_password_policy_rejects_weak(pw):
    with pytest.raises(ValueError):
        validate_password(pw)


@pytest.fixture
def auth_client(db_session, session_with_roles):
    app = create_app()
    refresh_store = InMemoryRefreshTokenStore()
    lockout = InMemoryLockoutStore(threshold=5)
    rst = InMemoryPasswordResetTokenStore()
    revoked = InMemoryRevokedTokenStore()
    rate_limiter = InMemoryRateLimiter()
    sent: list[dict] = []

    class FakeMailer:
        def send(self, *, to, subject, body_text, body_html=None):
            sent.append(
                {"to": to, "subject": subject, "body": body_text, "html": body_html}
            )

    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: refresh_store
    app.dependency_overrides[get_lockout_store] = lambda: lockout
    app.dependency_overrides[get_reset_token_store] = lambda: rst
    app.dependency_overrides[get_revoked_store] = lambda: revoked
    app.dependency_overrides[get_rate_limiter] = lambda: rate_limiter
    app.dependency_overrides[get_mailer] = lambda: FakeMailer()
    return TestClient(app), refresh_store, sent


def test_change_password_invalidates_old_access(auth_client):
    c, _, _ = auth_client
    reg = c.post("/api/auth/register",
                 json={"email": "kill@example.com", "password": "pw12345678"}).json()
    old_access = reg["access_token"]
    h = {"Authorization": f"Bearer {old_access}"}
    assert c.get("/api/auth/me", headers=h).status_code == 200
    assert c.put("/api/auth/password", headers=h,
                 json={"current_password": "pw12345678",
                       "new_password": "newpw12345"}).status_code == 200
    assert c.get("/api/auth/me", headers=h).status_code == 401
    login = c.post("/api/auth/login",
                   json={"email": "kill@example.com", "password": "newpw12345"})
    assert login.status_code == 200
    assert c.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    ).status_code == 200


def test_reset_confirm_invalidates_sessions(session_with_roles):
    session = session_with_roles
    store = InMemoryRefreshTokenStore()
    rst = InMemoryPasswordResetTokenStore()
    user, tokens = register_user(
        session, email="rstkill@example.com", password="pw12345678",
        display_name="R", refresh_store=store)
    session.flush()
    old_refresh = tokens.refresh_token
    token = request_password_reset(
        session, email="rstkill@example.com", reset_store=rst,
        lockout_store=InMemoryLockoutStore(threshold=5))
    confirm_password_reset(
        session, token=token, new_password="newpw12345",
        reset_store=rst, refresh_store=store)
    session.flush()
    assert store.load(old_refresh) is None
    assert user.tokens_invalid_before is not None


def test_mailer_called_on_reset_request(auth_client):
    c, _, sent = auth_client
    c.post("/api/auth/register",
           json={"email": "mailme@example.com", "password": "pw12345678"})
    r = c.post("/api/auth/reset-password/request",
               json={"email": "mailme@example.com"})
    assert r.status_code == 200
    assert len(sent) == 1
    assert sent[0]["to"] == "mailme@example.com"
    assert "forgot-password?token=" in sent[0]["body"]
