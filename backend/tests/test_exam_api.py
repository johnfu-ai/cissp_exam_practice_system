"""HTTP tests for fixed + CAT exam API (translations-based).

The ``client`` fixture builds a minimal FastAPI app mounting only the exam
router. The full ``create_app()`` cannot be used yet because sibling services
(``app.services.admin``) still import the removed ``Explanation`` model and are
rewritten in a later task (T9). Once that lands, this can revert to
``create_app()``.

Published bilingual questions are seeded directly via the question service
(not over HTTP) so the exam API surface is the only thing under test.
"""

import datetime as dt

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.exam import router as exam_router
from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.db.seed import PERMISSIONS
from app.db.session import get_session
from app.dependencies import get_lockout_store, get_refresh_store
from app.models.auth import OrganizationMembership, Role
from app.models.enums import QuestionType, RoleName
from app.schemas.question import (
    OptionIn,
    QuestionCreateIn,
    ReviewAction,
    TranslationIn,
    TranslationOptionIn,
)
from app.services.auth import InMemoryLockoutStore, register_user
from app.services.question import create_question, submit_review


@pytest.fixture
def client(db_session, session_with_roles):
    app = FastAPI()
    app.include_router(exam_router)
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
    return {"Authorization": f"Bearer {token}"}, user


def _seed_blueprint(db_session):
    """Seed a current exam blueprint + 1 domain (weight 100%)."""
    from app.models.taxonomy import ExamBlueprint, ExamDomain

    bp = ExamBlueprint(
        version_label="exam-v1", effective_date="2026-04-15",
        min_items=1, max_items=1, duration_minutes=30,
        passing_score=700, max_score=1000, is_current=True,
    )
    db_session.add(bp)
    db_session.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=100)
    db_session.add(dom)
    db_session.flush()
    return bp, dom


def _seed_bilingual_question(db_session, user, domain, *, difficulty=3):
    """Create + publish a bilingual single-choice question (option 0 correct)."""
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice,
        difficulty=difficulty,
        options=[
            OptionIn(order_index=0, is_correct=True),
            OptionIn(order_index=1, is_correct=False),
        ],
        translations=[
            TranslationIn(
                language="en", stem="What is 1+1?",
                correct_answer_rationale="Because 2.", key_point_summary="KP en",
                options=[
                    TranslationOptionIn(order_index=0, content="2", explanation="right"),
                    TranslationOptionIn(order_index=1, content="3", explanation="wrong"),
                ],
            ),
            TranslationIn(
                language="zh", stem="1+1等于几？",
                correct_answer_rationale="因为等于2。", key_point_summary="KP 中",
                options=[
                    TranslationOptionIn(order_index=0, content="二", explanation="对"),
                    TranslationOptionIn(order_index=1, content="三", explanation="错"),
                ],
            ),
        ],
    )
    q = create_question(
        db_session, org_id=user.default_organization_id, actor_id=user.id, payload=payload,
    )
    from app.models.question import QuestionMapping

    db_session.add(QuestionMapping(question_id=q.id, domain_id=domain.id))
    submit_review(db_session, question_id=q.id, actor_id=user.id, action=ReviewAction.submit)
    submit_review(db_session, question_id=q.id, actor_id=user.id, action=ReviewAction.approve)
    db_session.flush()
    return q


def _seed_en_only_question(db_session, user, domain, *, difficulty=3):
    """Create + publish an en-only single-choice question (option 0 correct)."""
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice,
        difficulty=difficulty,
        options=[
            OptionIn(order_index=0, is_correct=True),
            OptionIn(order_index=1, is_correct=False),
        ],
        translations=[
            TranslationIn(
                language="en", stem="en-only stem",
                correct_answer_rationale="en rationale", key_point_summary="en kp",
                options=[
                    TranslationOptionIn(order_index=0, content="A", explanation="en-A"),
                    TranslationOptionIn(order_index=1, content="B", explanation="en-B"),
                ],
            ),
        ],
    )
    q = create_question(
        db_session, org_id=user.default_organization_id, actor_id=user.id, payload=payload,
    )
    from app.models.question import QuestionMapping

    db_session.add(QuestionMapping(question_id=q.id, domain_id=domain.id))
    submit_review(db_session, question_id=q.id, actor_id=user.id, action=ReviewAction.submit)
    submit_review(db_session, question_id=q.id, actor_id=user.id, action=ReviewAction.approve)
    db_session.flush()
    return q


# --- fixed exam --------------------------------------------------------------


def test_fixed_happy_path_bilingual(client):
    c, store, db = client
    h, user = _headers(db, store, email="hp@example.com")
    _, dom = _seed_blueprint(db)
    _seed_bilingual_question(db, user, dom)
    # create
    s = c.post("/api/exam/sessions", json={}, headers=h)
    assert s.status_code == 200, s.text
    sid = s.json()["id"]
    assert s.json()["total_questions"] == 1
    assert s.json()["session_kind"] == "fixed"
    assert s.json()["config"]["language_mode"] == "en"
    # deliver — bilingual payload
    d = c.get(f"/api/exam/sessions/{sid}/questions/0", headers=h)
    assert d.status_code == 200, d.text
    body = d.json()
    assert body["available_languages"] == ["en", "zh"]
    assert body["language_mode"] == "en"
    assert body["stem"] == {"en": "What is 1+1?", "zh": "1+1等于几？"}
    assert body["options"][0]["content"] == {"en": "2", "zh": "二"}
    assert body["options"][1]["content"] == {"en": "3", "zh": "三"}
    assert "is_correct" not in body["options"][0]
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
    # review — bilingual
    rev = c.get(f"/api/exam/sessions/{sid}/review", headers=h)
    assert rev.status_code == 200, rev.text
    assert len(rev.json()) == 1
    item = rev.json()[0]
    assert item["your_answer"]["is_correct"] is True
    assert item["stem"] == {"en": "What is 1+1?", "zh": "1+1等于几？"}
    assert item["available_languages"] == ["en", "zh"]
    assert item["options"][0]["content"] == {"en": "2", "zh": "二"}
    assert item["options"][0]["explanation"] == {"en": "right", "zh": "对"}
    assert item["correct_rationale"] == {"en": "Because 2.", "zh": "因为等于2。"}
    # history
    hist = c.get("/api/exam/history", headers=h)
    assert hist.status_code == 200
    assert len(hist.json()) == 1
    assert hist.json()[0]["scaled_score"] == 1000


def test_fixed_review_before_finish_409(client):
    c, store, db = client
    h, user = _headers(db, store, email="bf@example.com")
    _, dom = _seed_blueprint(db)
    _seed_bilingual_question(db, user, dom)
    sid = c.post("/api/exam/sessions", json={}, headers=h).json()["id"]
    r = c.get(f"/api/exam/sessions/{sid}/review", headers=h)
    assert r.status_code == 409


def test_fixed_no_blueprint_422(client):
    c, store, db = client
    h, _ = _headers(db, store, email="nb@example.com")
    # no blueprint seeded
    r = c.post("/api/exam/sessions", json={}, headers=h)
    assert r.status_code == 422


def test_fixed_other_user_404(client):
    c, store, db = client
    h1, user = _headers(db, store, email="u1@example.com")
    h2, _ = _headers(db, store, email="u2@example.com")
    _, dom = _seed_blueprint(db)
    _seed_bilingual_question(db, user, dom)
    sid = c.post("/api/exam/sessions", json={}, headers=h1).json()["id"]
    assert c.get(f"/api/exam/sessions/{sid}/questions/0", headers=h2).status_code == 404
    assert c.get(f"/api/exam/sessions/{sid}", headers=h2).status_code == 404


def test_fixed_401_without_token(client):
    c, store, db = client
    assert c.post("/api/exam/sessions", json={}).status_code == 401


# --- CAT exam ----------------------------------------------------------------


def _seed_cat_pool(db_session, user, *, n=5, difficulty=3, min_items=1, max_items=3):
    from app.models.taxonomy import ExamBlueprint, ExamDomain

    bp = ExamBlueprint(
        version_label="cat-v1", effective_date="2026-04-15",
        min_items=min_items, max_items=max_items, duration_minutes=30,
        passing_score=700, max_score=1000, is_current=True,
    )
    db_session.add(bp); db_session.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=100)
    db_session.add(dom); db_session.flush()
    qs = []
    for i in range(n):
        q = _seed_bilingual_question(db_session, user, dom, difficulty=difficulty)
        qs.append(q)
    return bp, dom, qs


def test_cat_happy_path_bilingual(client):
    c, store, db = client
    h, user = _headers(db, store, email="cat-hp@example.com")
    _seed_cat_pool(db, user, n=5, difficulty=3, min_items=1, max_items=3)
    # create cat session
    s = c.post("/api/exam/sessions",
               json={"kind": "cat", "language_mode": "bilingual"}, headers=h)
    assert s.status_code == 200, s.text
    assert s.json()["session_kind"] == "cat"
    assert s.json()["config"]["language_mode"] == "bilingual"
    sid = s.json()["id"]
    # config must not leak internal CAT keys
    for key in ("question_ids", "next_question_id", "seen",
                "domain_targets", "domain_answered", "cat_params"):
        assert key not in s.json()["config"]
    assert "disclaimer" in s.json()["config"]
    assert "language_mode" in s.json()["config"]

    # deliver next item — bilingual
    d = c.get(f"/api/exam/sessions/{sid}/next", headers=h)
    assert d.status_code == 200, d.text
    body = d.json()
    assert body["position"] == 0
    assert body["total"] == 3
    assert body["language_mode"] == "bilingual"
    assert set(body["stem"].keys()) == {"en", "zh"}
    assert body["stem"]["en"] is not None
    assert body["stem"]["zh"] is not None
    for opt in body["options"]:
        assert "is_correct" not in opt
        assert opt["content"]["en"] is not None
        assert opt["content"]["zh"] is not None

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
    # review — bilingual
    rev = c.get(f"/api/exam/sessions/{sid}/review", headers=h)
    assert rev.status_code == 200, rev.text
    assert len(rev.json()) == pos + 1
    for item in rev.json():
        assert set(item["stem"].keys()) == {"en", "zh"}
        assert item["stem"]["en"] is not None
        assert item["stem"]["zh"] is not None
        assert item["available_languages"] == ["en", "zh"]
    # history
    hist = c.get("/api/exam/history", headers=h)
    assert hist.status_code == 200
    assert len(hist.json()) == 1
    assert hist.json()[0]["scaled_score"] > 500


def test_cat_next_on_fixed_session_409(client):
    c, store, db = client
    h, user = _headers(db, store, email="cat-fixed@example.com")
    _, dom = _seed_blueprint(db)
    _seed_bilingual_question(db, user, dom)
    sid = c.post("/api/exam/sessions", json={}, headers=h).json()["id"]
    r = c.get(f"/api/exam/sessions/{sid}/next", headers=h)
    assert r.status_code == 409


def test_cat_submit_wrong_position_422(client):
    c, store, db = client
    h, user = _headers(db, store, email="cat-pos@example.com")
    _seed_cat_pool(db, user, n=5, difficulty=3, min_items=1, max_items=5)
    sid = c.post("/api/exam/sessions", json={"kind": "cat"}, headers=h).json()["id"]
    r = c.post(f"/api/exam/sessions/{sid}/answers",
               json={"position": 5, "selected": [0],
                     "started_at": dt.datetime.now(dt.timezone.utc).isoformat()},
               headers=h)
    assert r.status_code == 422


def test_cat_other_user_404(client):
    c, store, db = client
    h1, user = _headers(db, store, email="cat-owner@example.com")
    h2, _ = _headers(db, store, email="cat-intruder@example.com")
    _seed_cat_pool(db, user, n=5, difficulty=3, min_items=1, max_items=3)
    sid = c.post("/api/exam/sessions", json={"kind": "cat"}, headers=h1).json()["id"]
    assert c.get(f"/api/exam/sessions/{sid}/next", headers=h2).status_code == 404


def test_cat_401_without_token(client):
    c, store, db = client
    # Seed an org/user (token unused) so the CAT pool can be populated; the
    # assertion is that the unauthenticated POST is rejected with 401 before
    # any session-creation logic runs.
    h, user = _headers(db, store, email="cat-anon@example.com")
    _seed_cat_pool(db, user, n=5, difficulty=3, min_items=1, max_items=3)
    assert c.post("/api/exam/sessions", json={"kind": "cat"}).status_code == 401
