"""HTTP tests for user preference API (language_mode).

The ``auth_client`` fixture builds a minimal FastAPI app mounting only the
auth + users routers. The full ``create_app()`` cannot be used yet because
``app.services.admin`` still imports the removed ``Explanation`` model (fixed
in T9), which makes ``create_app()`` raise at import time and breaks
collection of any test module that imports it (e.g. ``tests/test_auth_api.py``).
Mounting just the two import-clean routers under test keeps these tests
independent of the broken admin service. Once T9 lands, this can revert to
``create_app()``.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.core.security import InMemoryRefreshTokenStore
from app.db.session import get_session
from app.dependencies import get_lockout_store, get_refresh_store
from app.services.auth import InMemoryLockoutStore


@pytest.fixture
def auth_client(db_session, session_with_roles):
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(users_router)
    store = InMemoryRefreshTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: store
    app.dependency_overrides[get_lockout_store] = lambda: InMemoryLockoutStore()
    return TestClient(app)


def _register(auth_client, email="pref@example.com"):
    resp = auth_client.post(
        "/api/auth/register",
        json={"email": email, "password": "pw123456", "display_name": "Pref"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_me_returns_language_mode(auth_client):
    token = _register(auth_client)
    r = auth_client.get("/api/auth/me", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["language_mode"] in ("en", "zh", "bilingual")


def test_me_default_language_mode_is_en(auth_client):
    token = _register(auth_client)
    r = auth_client.get("/api/auth/me", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["language_mode"] == "en"


def test_get_preferences_returns_default(auth_client):
    token = _register(auth_client)
    r = auth_client.get("/api/users/me/preferences", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["language_mode"] == "en"


def test_put_preferences_updates_default(auth_client):
    token = _register(auth_client)
    r = auth_client.put(
        "/api/users/me/preferences",
        json={"language_mode": "zh"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["language_mode"] == "zh"
    # subsequent /me reflects the new default
    me = auth_client.get("/api/auth/me", headers=_auth(token)).json()
    assert me["language_mode"] == "zh"
    # and the GET preferences endpoint reflects it too
    prefs = auth_client.get("/api/users/me/preferences", headers=_auth(token)).json()
    assert prefs["language_mode"] == "zh"


def test_put_preferences_bilingual(auth_client):
    token = _register(auth_client)
    r = auth_client.put(
        "/api/users/me/preferences",
        json={"language_mode": "bilingual"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["language_mode"] == "bilingual"


def test_put_preferences_rejects_invalid(auth_client):
    token = _register(auth_client)
    r = auth_client.put(
        "/api/users/me/preferences",
        json={"language_mode": "fr"},
        headers=_auth(token),
    )
    assert r.status_code == 422


def test_preferences_require_auth(auth_client):
    assert auth_client.get("/api/users/me/preferences").status_code == 401
    assert auth_client.put(
        "/api/users/me/preferences", json={"language_mode": "zh"}
    ).status_code == 401


def test_get_preferences_returns_interface_language(auth_client):
    token = _register(auth_client)
    prefs = auth_client.get("/api/users/me/preferences", headers=_auth(token)).json()
    assert prefs["interface_language"] == "en"


def test_me_default_interface_language_is_en(auth_client):
    token = _register(auth_client)
    r = auth_client.get("/api/auth/me", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["interface_language"] == "en"


def test_put_preferences_sets_interface_language(auth_client):
    token = _register(auth_client)
    r = auth_client.put(
        "/api/users/me/preferences",
        json={"interface_language": "zh"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["interface_language"] == "zh"
    me = auth_client.get("/api/auth/me", headers=_auth(token)).json()
    assert me["interface_language"] == "zh"
    prefs = auth_client.get("/api/users/me/preferences", headers=_auth(token)).json()
    assert prefs["interface_language"] == "zh"


def test_put_preferences_rejects_invalid_interface_language(auth_client):
    token = _register(auth_client)
    r = auth_client.put(
        "/api/users/me/preferences",
        json={"interface_language": "fr"},
        headers=_auth(token),
    )
    assert r.status_code == 422


def test_put_preferences_rejects_bilingual_interface_language(auth_client):
    token = _register(auth_client)
    r = auth_client.put(
        "/api/users/me/preferences",
        json={"interface_language": "bilingual"},
        headers=_auth(token),
    )
    assert r.status_code == 422


def test_put_preferences_updates_both_fields(auth_client):
    token = _register(auth_client)
    r = auth_client.put(
        "/api/users/me/preferences",
        json={"language_mode": "bilingual", "interface_language": "zh"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["language_mode"] == "bilingual"
    assert body["interface_language"] == "zh"


def test_put_preferences_rejects_empty_body(auth_client):
    token = _register(auth_client)
    r = auth_client.put(
        "/api/users/me/preferences",
        json={},
        headers=_auth(token),
    )
    assert r.status_code == 422
