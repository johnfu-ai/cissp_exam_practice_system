"""HTTP tests for practice API (sub-project E)."""

import datetime as dt

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


def _headers(db_session, store, email="learn@example.com",
             role=RoleName.individual_learner, perms=None):
    user, _ = register_user(
        db_session, email=email, password="pw123456",
        display_name="L", refresh_store=store,
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


def _seed_question(c, h, stem="q"):
    body = {
        "question_type": "single_choice",
        "stem": stem,
        "stem_format": "markdown",
        "status": "published",
        "options": [
            {"content": "A", "is_correct": True, "order_index": 0},
            {"content": "B", "is_correct": False, "order_index": 1},
        ],
    }
    r = c.post("/api/questions", json=body, headers=h)
    assert r.status_code == 200, r.text
    qid = r.json()["id"]
    # created as draft -> publish via the review state machine
    assert c.post(f"/api/questions/{qid}/review", json={"action": "submit"}, headers=h).status_code == 200
    assert c.post(f"/api/questions/{qid}/review", json={"action": "approve"}, headers=h).status_code == 200
    return qid


def test_happy_path(client):
    c, store, db = client
    h = _headers(db, store, email="hp@example.com")
    _seed_question(c, h, "q1")
    # create session
    s = c.post("/api/practice/sessions", json={"count": 1, "order_mode": "sequential"},
               headers=h)
    assert s.status_code == 200, s.text
    sid = s.json()["id"]
    # deliver
    d = c.get(f"/api/practice/sessions/{sid}/questions/0", headers=h)
    assert d.status_code == 200
    assert d.json()["total"] == 1
    # answer
    a = c.post(
        f"/api/practice/sessions/{sid}/answers",
        json={"position": 0, "selected": [0],
              "started_at": dt.datetime.now(dt.timezone.utc).isoformat()},
        headers=h,
    )
    assert a.status_code == 200, a.text
    assert a.json()["is_correct"] is True
    # finish + summary
    fin = c.post(f"/api/practice/sessions/{sid}/finish", headers=h)
    assert fin.status_code == 200, fin.text
    assert fin.json()["accuracy"] == 1.0


def test_reanswer_conflict_409(client):
    c, store, db = client
    h = _headers(db, store, email="ra@example.com")
    _seed_question(c, h)
    sid = c.post("/api/practice/sessions",
                 json={"count": 1, "order_mode": "sequential"}, headers=h).json()["id"]
    body = {"position": 0, "selected": [0],
            "started_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    assert c.post(f"/api/practice/sessions/{sid}/answers", json=body, headers=h).status_code == 200
    assert c.post(f"/api/practice/sessions/{sid}/answers", json=body, headers=h).status_code == 409


def test_empty_scope_422(client):
    c, store, db = client
    h = _headers(db, store, email="empty@example.com")
    r = c.post("/api/practice/sessions", json={"count": 10}, headers=h)
    assert r.status_code == 422


def test_other_user_404(client):
    c, store, db = client
    h1 = _headers(db, store, email="u1@example.com")
    h2 = _headers(db, store, email="u2@example.com")
    _seed_question(c, h1)
    sid = c.post("/api/practice/sessions",
                 json={"count": 1, "order_mode": "sequential"}, headers=h1).json()["id"]
    assert c.get(f"/api/practice/sessions/{sid}/questions/0", headers=h2).status_code == 404


def test_401_without_token(client):
    c, store, db = client
    assert c.post("/api/practice/sessions", json={"count": 1}).status_code == 401
