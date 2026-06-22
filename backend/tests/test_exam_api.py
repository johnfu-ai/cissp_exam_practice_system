"""HTTP tests for fixed exam API (sub-project F)."""

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


def _headers(db_session, store, email="exam@example.com",
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


def _seed_blueprint_and_question(db, *, min_items=1, max_items=1):
    """Seed a current blueprint + 1 domain + 1 published question (mapped)."""
    from app.models.enums import QuestionStatus, QuestionType, TextFormat
    from app.models.question import Question, QuestionMapping, QuestionOption
    from app.models.taxonomy import ExamBlueprint, ExamDomain
    from app.models.auth import Organization, User

    org = db.query(Organization).first()
    actor = db.query(User).first()
    bp = ExamBlueprint(
        version_label="exam-v1", effective_date="2026-04-15",
        min_items=min_items, max_items=max_items, duration_minutes=30,
        passing_score=700, max_score=1000, is_current=True,
    )
    db.add(bp)
    db.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=100)
    db.add(dom)
    db.flush()
    q = Question(
        organization_id=org.id, question_type=QuestionType.single_choice,
        stem="q1", stem_format=TextFormat.markdown, status=QuestionStatus.published,
        created_by_id=actor.id,
    )
    db.add(q)
    db.flush()
    db.add(QuestionOption(
        question_id=q.id, order_index=0, content="A",
        content_format=TextFormat.markdown, is_correct=True))
    db.add(QuestionOption(
        question_id=q.id, order_index=1, content="B",
        content_format=TextFormat.markdown, is_correct=False))
    db.add(QuestionMapping(question_id=q.id, domain_id=dom.id))
    db.flush()
    return q


def test_happy_path(client):
    c, store, db = client
    h = _headers(db, store, email="hp@example.com")
    _seed_blueprint_and_question(db, min_items=1, max_items=1)
    # create
    s = c.post("/api/exam/sessions", json={}, headers=h)
    assert s.status_code == 200, s.text
    sid = s.json()["id"]
    assert s.json()["total_questions"] == 1
    assert s.json()["session_kind"] == "fixed"
    # deliver
    d = c.get(f"/api/exam/sessions/{sid}/questions/0", headers=h)
    assert d.status_code == 200, d.text
    assert "is_correct" not in d.json()["options"][0]
    # answer (no judgment returned)
    a = c.post(
        f"/api/exam/sessions/{sid}/answers",
        json={"position": 0, "selected": [0],
              "started_at": dt.datetime.now(dt.timezone.utc).isoformat()},
        headers=h,
    )
    assert a.status_code == 200, a.text
    assert "is_correct" not in a.json()
    assert a.json()["saved"] is True
    # finish -> report
    fin = c.post(f"/api/exam/sessions/{sid}/finish", headers=h)
    assert fin.status_code == 200, fin.text
    assert fin.json()["correct_count"] == 1
    assert fin.json()["scaled_score"] == 1000
    assert fin.json()["passed"] is True
    # review
    rev = c.get(f"/api/exam/sessions/{sid}/review", headers=h)
    assert rev.status_code == 200, rev.text
    assert len(rev.json()) == 1
    assert rev.json()[0]["your_answer"]["is_correct"] is True
    # history
    hist = c.get("/api/exam/history", headers=h)
    assert hist.status_code == 200
    assert len(hist.json()) == 1
    assert hist.json()[0]["scaled_score"] == 1000


def test_review_before_finish_409(client):
    c, store, db = client
    h = _headers(db, store, email="bf@example.com")
    _seed_blueprint_and_question(db)
    sid = c.post("/api/exam/sessions", json={}, headers=h).json()["id"]
    r = c.get(f"/api/exam/sessions/{sid}/review", headers=h)
    assert r.status_code == 409


def test_no_blueprint_422(client):
    c, store, db = client
    h = _headers(db, store, email="nb@example.com")
    r = c.post("/api/exam/sessions", json={}, headers=h)
    assert r.status_code == 422


def test_other_user_404(client):
    c, store, db = client
    h1 = _headers(db, store, email="u1@example.com")
    h2 = _headers(db, store, email="u2@example.com")
    _seed_blueprint_and_question(db)
    sid = c.post("/api/exam/sessions", json={}, headers=h1).json()["id"]
    assert c.get(f"/api/exam/sessions/{sid}/questions/0", headers=h2).status_code == 404
    assert c.get(f"/api/exam/sessions/{sid}", headers=h2).status_code == 404


def test_401_without_token(client):
    c, store, db = client
    assert c.post("/api/exam/sessions", json={}).status_code == 401
