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


def _seed_cat_pool(db, *, n=5, difficulty=3, min_items=1, max_items=5):
    from app.models.enums import QuestionStatus, QuestionType, TextFormat
    from app.models.question import Question, QuestionMapping, QuestionOption
    from app.models.taxonomy import ExamBlueprint, ExamDomain
    from app.models.auth import Organization, User

    org = db.query(Organization).first()
    actor = db.query(User).first()
    bp = ExamBlueprint(
        version_label="cat-v1", effective_date="2026-04-15",
        min_items=min_items, max_items=max_items, duration_minutes=30,
        passing_score=700, max_score=1000, is_current=True,
    )
    db.add(bp); db.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=100)
    db.add(dom); db.flush()
    qs = []
    for i in range(n):
        q = Question(
            organization_id=org.id, question_type=QuestionType.single_choice,
            stem=f"cat-q{i}", stem_format=TextFormat.markdown,
            status=QuestionStatus.published, created_by_id=actor.id,
            difficulty=difficulty,
        )
        db.add(q); db.flush()
        db.add(QuestionOption(question_id=q.id, order_index=0, content="A",
                              content_format=TextFormat.markdown, is_correct=True))
        db.add(QuestionOption(question_id=q.id, order_index=1, content="B",
                              content_format=TextFormat.markdown, is_correct=False))
        db.add(QuestionMapping(question_id=q.id, domain_id=dom.id))
        qs.append(q)
    db.flush()
    return bp, qs


def test_cat_happy_path(client):
    c, store, db = client
    h = _headers(db, store, email="cat-hp@example.com")
    _seed_cat_pool(db, n=5, difficulty=3, min_items=1, max_items=3)
    # create cat session
    s = c.post("/api/exam/sessions", json={"kind": "cat"}, headers=h)
    assert s.status_code == 200, s.text
    assert s.json()["session_kind"] == "cat"
    sid = s.json()["id"]
    # config must not leak internal CAT keys
    for key in ("question_ids", "next_question_id", "seen",
                "domain_targets", "domain_answered", "cat_params"):
        assert key not in s.json()["config"]
    assert "disclaimer" in s.json()["config"]

    # deliver next item
    d = c.get(f"/api/exam/sessions/{sid}/next", headers=h)
    assert d.status_code == 200, d.text
    assert d.json()["position"] == 0
    assert d.json()["total"] == 3
    assert "is_correct" not in d.json()["options"][0]

    # answer all (max_items=3) -> auto-finish
    pos = 0
    ack = c.post(f"/api/exam/sessions/{sid}/answers",
                 json={"position": pos, "selected": [0],
                       "started_at": dt.datetime.now(dt.timezone.utc).isoformat()},
                 headers=h)
    assert ack.status_code == 200, ack.text
    while not ack.json().get("finished"):
        pos += 1
        ack = c.post(f"/api/exam/sessions/{sid}/answers",
                     json={"position": pos, "selected": [0],
                           "started_at": dt.datetime.now(dt.timezone.utc).isoformat()},
                     headers=h)
        assert ack.status_code == 200, ack.text
    # report
    rep = c.get(f"/api/exam/sessions/{sid}/report", headers=h)
    assert rep.status_code == 200, rep.text
    assert rep.json()["ability_estimate"] is not None
    assert rep.json()["readiness_level"] in {"ready", "almost_ready", "developing", "needs_work"}
    assert rep.json()["disclaimer"]
    # review
    rev = c.get(f"/api/exam/sessions/{sid}/review", headers=h)
    assert rev.status_code == 200, rev.text
    assert len(rev.json()) == pos + 1
    # history
    hist = c.get("/api/exam/history", headers=h)
    assert hist.status_code == 200
    assert len(hist.json()) == 1
    assert hist.json()[0]["scaled_score"] > 500


def test_cat_next_on_fixed_session_409(client):
    c, store, db = client
    h = _headers(db, store, email="cat-fixed@example.com")
    _seed_blueprint_and_question(db, min_items=1, max_items=1)
    sid = c.post("/api/exam/sessions", json={}, headers=h).json()["id"]
    r = c.get(f"/api/exam/sessions/{sid}/next", headers=h)
    assert r.status_code == 409


def test_cat_submit_wrong_position_422(client):
    c, store, db = client
    h = _headers(db, store, email="cat-pos@example.com")
    _seed_cat_pool(db, n=5, difficulty=3, min_items=1, max_items=5)
    sid = c.post("/api/exam/sessions", json={"kind": "cat"}, headers=h).json()["id"]
    r = c.post(f"/api/exam/sessions/{sid}/answers",
               json={"position": 5, "selected": [0],
                     "started_at": dt.datetime.now(dt.timezone.utc).isoformat()},
               headers=h)
    assert r.status_code == 422


def test_cat_other_user_404(client):
    c, store, db = client
    h1 = _headers(db, store, email="cat-owner@example.com")
    h2 = _headers(db, store, email="cat-intruder@example.com")
    _seed_cat_pool(db, n=5, difficulty=3, min_items=1, max_items=3)
    sid = c.post("/api/exam/sessions", json={"kind": "cat"}, headers=h1).json()["id"]
    assert c.get(f"/api/exam/sessions/{sid}/next", headers=h2).status_code == 404


def test_cat_401_without_token(client):
    c, store, db = client
    # Seed an org/user (token unused) so the CAT pool can be populated; the
    # assertion is that the unauthenticated POST is rejected with 401 before
    # any session-creation logic runs.
    _headers(db, store, email="cat-anon@example.com")
    _seed_cat_pool(db, n=5, difficulty=3, min_items=1, max_items=3)
    assert c.post("/api/exam/sessions", json={"kind": "cat"}).status_code == 401
