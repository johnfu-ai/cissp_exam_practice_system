import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.dependencies import CurrentUser, get_current_user, get_refresh_store, require_permission
from app.db.session import get_session
from app.models.auth import Organization, OrganizationMembership, Role, User
from app.models.enums import OrgKind, RoleName
from app.services.auth import InMemoryLockoutStore, register_user


def _build_app(db_session, refresh_store):
    app = FastAPI()

    def _session():
        yield db_session
    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_refresh_store] = lambda: refresh_store

    @app.get("/me")
    def me(current: CurrentUser = Depends(get_current_user)):
        return {"email": current.user.email, "perms": current.perms}

    @app.get("/admin")
    def admin(current: CurrentUser = Depends(require_permission("admin:manage_taxonomy"))):
        return {"ok": True}
    return app


def _make_user(db_session, refresh_store, email="dep@example.com"):
    user, _ = register_user(db_session, email=email, password="pw123456",
                            display_name="Dep", refresh_store=refresh_store)
    db_session.flush()
    # grant system_admin role on the personal org for the admin test
    sa_role = db_session.query(Role).filter_by(name=RoleName.system_admin).first()
    if sa_role is None:
        sa_role = Role(name=RoleName.system_admin, description="sysadmin")
        db_session.add(sa_role); db_session.flush()
    m = db_session.query(OrganizationMembership).filter_by(user_id=user.id).one()
    m.role_id = sa_role.id
    db_session.flush()
    return user


def test_no_token_returns_401(db_session, session_with_roles):
    refresh_store = InMemoryRefreshTokenStore()
    app = _build_app(db_session, refresh_store)
    client = TestClient(app)
    resp = client.get("/me")
    assert resp.status_code == 401


def test_valid_token_returns_user(db_session, session_with_roles):
    refresh_store = InMemoryRefreshTokenStore()
    user = _make_user(db_session, refresh_store)
    token = create_access_token(user_id=user.id, org_id=user.default_organization_id,
                                roles=["system_admin"], perms=["admin:manage_taxonomy"])
    app = _build_app(db_session, refresh_store)
    client = TestClient(app)
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "dep@example.com"


def test_require_permission_denies_without_perm(db_session, session_with_roles):
    refresh_store = InMemoryRefreshTokenStore()
    # plain learner (no admin perms)
    user, _ = register_user(db_session, email="learner@example.com", password="pw123456",
                            display_name="L", refresh_store=refresh_store)
    db_session.flush()
    token = create_access_token(user_id=user.id, org_id=user.default_organization_id,
                                roles=["individual_learner"], perms=["question:read"])
    app = _build_app(db_session, refresh_store)
    client = TestClient(app)
    resp = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_require_permission_allows_with_perm(db_session, session_with_roles):
    refresh_store = InMemoryRefreshTokenStore()
    user = _make_user(db_session, refresh_store, email="admin2@example.com")
    token = create_access_token(user_id=user.id, org_id=user.default_organization_id,
                                roles=["system_admin"], perms=["admin:manage_taxonomy"])
    app = _build_app(db_session, refresh_store)
    client = TestClient(app)
    resp = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
