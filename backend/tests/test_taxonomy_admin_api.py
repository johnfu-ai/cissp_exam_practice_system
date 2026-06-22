"""HTTP tests for taxonomy admin (sub-project D)."""

import pytest
from fastapi.testclient import TestClient

from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.db.seed import PERMISSIONS
from app.db.session import get_session
from app.dependencies import get_lockout_store, get_refresh_store
from app.main import create_app
from app.models.auth import OrganizationMembership, Role
from app.models.enums import RoleName
from app.services.auth import InMemoryLockoutStore, register_user


@pytest.fixture
def client(db_session, session_with_roles):
    app = create_app()
    store = InMemoryRefreshTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: store
    app.dependency_overrides[get_lockout_store] = lambda: InMemoryLockoutStore()
    return TestClient(app), store, db_session


def _headers(db_session, store, email="a@example.com", role=RoleName.system_admin,
             perms=None):
    user, _ = register_user(
        db_session, email=email, password="pw123456",
        display_name="A", refresh_store=store,
    )
    db_session.flush()
    r = db_session.query(Role).filter_by(name=role).first()
    m = db_session.query(OrganizationMembership).filter_by(user_id=user.id).one()
    m.role_id = r.id
    db_session.flush()
    if perms is None:
        perms = [c for c, _ in PERMISSIONS]
    token = create_access_token(
        user_id=user.id, org_id=user.default_organization_id,
        roles=[role.value], perms=perms,
    )
    return {"Authorization": f"Bearer {token}"}


def _bp_body(**kw):
    body = dict(
        version_label="2026-04-15", effective_date="2026-04-15",
        min_items=100, max_items=150, duration_minutes=180,
        passing_score=700, max_score=1000,
    )
    body.update(kw)
    return body


# --- ExamBlueprint ---


def test_blueprint_create_and_get(client):
    c, store, db = client
    h = _headers(db, store, email="bp1@example.com")
    resp = c.post("/api/admin/blueprints", json=_bp_body(), headers=h)
    assert resp.status_code == 200, resp.text
    bpid = resp.json()["id"]
    got = c.get(f"/api/admin/blueprints/{bpid}", headers=h)
    assert got.status_code == 200
    assert got.json()["domains"] == []


def test_blueprint_create_validation_422(client):
    c, store, db = client
    h = _headers(db, store, email="bp2@example.com")
    assert c.post(
        "/api/admin/blueprints",
        json=_bp_body(min_items=200, max_items=100), headers=h,
    ).status_code == 422


def test_blueprint_set_current(client):
    c, store, db = client
    h = _headers(db, store, email="bp3@example.com")
    a = c.post("/api/admin/blueprints", json=_bp_body(version_label="a"),
               headers=h).json()["id"]
    b = c.post("/api/admin/blueprints", json=_bp_body(version_label="b"),
               headers=h).json()["id"]
    assert c.post(f"/api/admin/blueprints/{a}/set-current",
                  headers=h).status_code == 200
    assert c.get(f"/api/admin/blueprints/{a}", headers=h).json()["is_current"] is True
    assert c.get(f"/api/admin/blueprints/{b}", headers=h).json()["is_current"] is False


def test_blueprint_list(client):
    c, store, db = client
    h = _headers(db, store, email="bp4@example.com")
    c.post("/api/admin/blueprints", json=_bp_body(version_label="a"), headers=h)
    c.post("/api/admin/blueprints", json=_bp_body(version_label="b"), headers=h)
    assert len(c.get("/api/admin/blueprints", headers=h).json()) == 2


def test_blueprint_update(client):
    c, store, db = client
    h = _headers(db, store, email="bp5@example.com")
    bpid = c.post("/api/admin/blueprints", json=_bp_body(), headers=h).json()["id"]
    put = c.put(f"/api/admin/blueprints/{bpid}",
                json={"max_items": 160}, headers=h)
    assert put.status_code == 200, put.text
    assert put.json()["max_items"] == 160


def test_blueprint_delete(client):
    c, store, db = client
    h = _headers(db, store, email="bp6@example.com")
    bpid = c.post("/api/admin/blueprints", json=_bp_body(), headers=h).json()["id"]
    assert c.delete(f"/api/admin/blueprints/{bpid}", headers=h).status_code == 200
    assert c.get(f"/api/admin/blueprints/{bpid}", headers=h).status_code == 404


# --- ExamDomain ---


def test_domain_create_and_list(client):
    c, store, db = client
    h = _headers(db, store, email="dm1@example.com")
    bpid = c.post("/api/admin/blueprints", json=_bp_body(), headers=h).json()["id"]
    resp = c.post(
        f"/api/admin/blueprints/{bpid}/domains",
        json={"number": 1, "name": "D1", "weight_pct": 12}, headers=h,
    )
    assert resp.status_code == 200, resp.text
    lst = c.get(f"/api/admin/blueprints/{bpid}/domains", headers=h)
    assert len(lst.json()) == 1


def test_domain_weight_422(client):
    c, store, db = client
    h = _headers(db, store, email="dm2@example.com")
    bpid = c.post("/api/admin/blueprints", json=_bp_body(), headers=h).json()["id"]
    assert c.post(
        f"/api/admin/blueprints/{bpid}/domains",
        json={"number": 1, "name": "D1", "weight_pct": 200}, headers=h,
    ).status_code == 422


def test_domain_duplicate_409(client):
    c, store, db = client
    h = _headers(db, store, email="dm3@example.com")
    bpid = c.post("/api/admin/blueprints", json=_bp_body(), headers=h).json()["id"]
    c.post(f"/api/admin/blueprints/{bpid}/domains",
           json={"number": 1, "name": "D1", "weight_pct": 10}, headers=h)
    assert c.post(
        f"/api/admin/blueprints/{bpid}/domains",
        json={"number": 1, "name": "D2", "weight_pct": 10}, headers=h,
    ).status_code == 409


# --- Permission gate ---


def test_admin_403_for_learner(client):
    c, store, db = client
    h = _headers(
        db, store, email="no@example.com", role=RoleName.individual_learner,
        perms=["question:read", "practice:read", "exam:read"],
    )
    assert c.post("/api/admin/blueprints", json=_bp_body(),
                  headers=h).status_code == 403


def test_admin_401_without_token(client):
    c, store, db = client
    assert c.post("/api/admin/blueprints", json=_bp_body()).status_code == 401


# --- Book / Chapter ---


def test_book_create_get_update(client):
    c, store, db = client
    h = _headers(db, store, email="bk1@example.com")
    r = c.post("/api/books", json={"title": "OSG", "edition": "10th"}, headers=h)
    assert r.status_code == 200, r.text
    bid = r.json()["id"]
    assert c.get(f"/api/books/{bid}", headers=h).json()["title"] == "OSG"
    put = c.put(f"/api/books/{bid}", json={"title": "OSG2"}, headers=h)
    assert put.status_code == 200
    assert put.json()["title"] == "OSG2"


def test_chapter_create(client):
    c, store, db = client
    h = _headers(db, store, email="bk2@example.com")
    bid = c.post("/api/books", json={"title": "B"}, headers=h).json()["id"]
    r = c.post(
        f"/api/books/{bid}/chapters",
        json={"order_index": 0, "title": "C1"}, headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["book_id"] == bid


# --- KnowledgePoint + binding ---


def test_kp_create_cycle_422(client):
    c, store, db = client
    h = _headers(db, store, email="kp1@example.com")
    root = c.post("/api/knowledge-points", json={"name": "root"}, headers=h).json()["id"]
    child = c.post(
        "/api/knowledge-points", json={"name": "child", "parent_id": root},
        headers=h,
    ).json()["id"]
    # setting root's parent to child -> cycle -> 422
    assert c.put(
        f"/api/knowledge-points/{root}",
        json={"name": "root", "parent_id": child}, headers=h,
    ).status_code == 422


def test_kp_binding_list(client):
    c, store, db = client
    h = _headers(db, store, email="kp2@example.com")
    bpid = c.post("/api/admin/blueprints", json=_bp_body(), headers=h).json()["id"]
    did = c.post(
        f"/api/admin/blueprints/{bpid}/domains",
        json={"number": 1, "name": "D1", "weight_pct": 10}, headers=h,
    ).json()["id"]
    kid = c.post("/api/knowledge-points", json={"name": "KP"}, headers=h).json()["id"]
    r = c.post(
        f"/api/admin/knowledge-points/{kid}/domains",
        json={"domain_id": did}, headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["id"] == did
    lst = c.get(f"/api/admin/knowledge-points/{kid}/domains", headers=h)
    assert len(lst.json()) == 1


# --- Tag ---


def test_tag_create_duplicate_409(client):
    c, store, db = client
    h = _headers(db, store, email="tg1@example.com")
    assert c.post("/api/tags", json={"name": "crypto"}, headers=h).status_code == 200
    assert c.post(
        "/api/tags", json={"name": "crypto"}, headers=h
    ).status_code == 409
    assert len(c.get("/api/tags", headers=h).json()) == 1
