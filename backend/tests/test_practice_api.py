"""HTTP tests for practice API (translations-based).

The ``client`` fixture builds a minimal FastAPI app mounting only the practice
router. The full ``create_app()`` cannot be used yet because sibling services
(``app.services.admin``/``exam``) still import the removed ``Explanation``
model and are rewritten in later tasks (T6/T9). Once those land, this can
revert to ``create_app()``.

Published bilingual questions are seeded directly via the question service
(not over HTTP) so the practice API surface is the only thing under test.
"""

import datetime as dt

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.practice import router as practice_router
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
    app.include_router(practice_router)
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
    return {"Authorization": f"Bearer {token}"}, user


def _seed_bilingual_question(db_session, user):
    """Create + publish a bilingual single-choice question (option 0 correct)."""
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice,
        options=[
            OptionIn(order_index=0, is_correct=True),
            OptionIn(order_index=1, is_correct=False),
        ],
        translations=[
            TranslationIn(
                language="en", stem="What is 1+1?", correct_answer_rationale="Because 2.",
                options=[
                    TranslationOptionIn(order_index=0, content="2", explanation="right"),
                    TranslationOptionIn(order_index=1, content="3", explanation="wrong"),
                ],
            ),
            TranslationIn(
                language="zh", stem="1+1等于几？", correct_answer_rationale="因为等于2。",
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
    submit_review(db_session, question_id=q.id, actor_id=user.id, action=ReviewAction.submit)
    submit_review(db_session, question_id=q.id, actor_id=user.id, action=ReviewAction.approve)
    db_session.flush()
    return q


def test_happy_path(client):
    c, store, db = client
    h, user = _headers(db, store, email="hp@example.com")
    _seed_bilingual_question(db, user)
    # create session
    s = c.post("/api/practice/sessions",
               json={"count": 1, "order_mode": "sequential"}, headers=h)
    assert s.status_code == 200, s.text
    sid = s.json()["id"]
    assert s.json()["config"]["language_mode"] == "en"
    # deliver — bilingual payload
    d = c.get(f"/api/practice/sessions/{sid}/questions/0", headers=h)
    assert d.status_code == 200, d.text
    body = d.json()
    assert body["total"] == 1
    assert body["available_languages"] == ["en", "zh"]
    assert body["language_mode"] == "en"
    assert body["stem"] == {"en": "What is 1+1?", "zh": "1+1等于几？"}
    assert body["options"][0]["content"] == {"en": "2", "zh": "二"}
    assert body["options"][1]["content"] == {"en": "3", "zh": "三"}
    assert "is_correct" not in body["options"][0]
    # answer
    a = c.post(
        f"/api/practice/sessions/{sid}/answers",
        json={"position": 0, "selected": [0],
              "started_at": dt.datetime.now(dt.timezone.utc).isoformat()},
        headers=h,
    )
    assert a.status_code == 200, a.text
    ab = a.json()
    assert ab["is_correct"] is True
    assert ab["correct_indexes"] == [0]
    assert ab["correct_rationale"] == {"en": "Because 2.", "zh": "因为等于2。"}
    assert ab["per_option"][0]["explanation"] == {"en": "right", "zh": "对"}
    # finish + summary
    fin = c.post(f"/api/practice/sessions/{sid}/finish", headers=h)
    assert fin.status_code == 200, fin.text
    assert fin.json()["accuracy"] == 1.0


def test_session_uses_payload_language_mode(client):
    """Explicit payload language_mode overrides user default + stamps config."""
    c, store, db = client
    h, user = _headers(db, store, email="mode@example.com")
    _seed_bilingual_question(db, user)
    s = c.post(
        "/api/practice/sessions",
        json={"count": 1, "order_mode": "sequential", "language_mode": "bilingual"},
        headers=h,
    )
    assert s.status_code == 200, s.text
    assert s.json()["config"]["language_mode"] == "bilingual"


def test_reanswer_conflict_409(client):
    c, store, db = client
    h, user = _headers(db, store, email="ra@example.com")
    _seed_bilingual_question(db, user)
    sid = c.post("/api/practice/sessions",
                 json={"count": 1, "order_mode": "sequential"}, headers=h).json()["id"]
    body = {"position": 0, "selected": [0],
            "started_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    assert c.post(f"/api/practice/sessions/{sid}/answers", json=body, headers=h).status_code == 200
    assert c.post(f"/api/practice/sessions/{sid}/answers", json=body, headers=h).status_code == 409


def test_empty_scope_422(client):
    c, store, db = client
    h, _ = _headers(db, store, email="empty@example.com")
    r = c.post("/api/practice/sessions", json={"count": 10}, headers=h)
    assert r.status_code == 422


def test_other_user_404(client):
    c, store, db = client
    h1, user = _headers(db, store, email="u1@example.com")
    h2, _ = _headers(db, store, email="u2@example.com")
    _seed_bilingual_question(db, user)
    sid = c.post("/api/practice/sessions",
                 json={"count": 1, "order_mode": "sequential"}, headers=h1).json()["id"]
    assert c.get(f"/api/practice/sessions/{sid}/questions/0", headers=h2).status_code == 404


def test_401_without_token(client):
    c, store, db = client
    assert c.post("/api/practice/sessions", json={"count": 1}).status_code == 401


def test_set_question_state_returns_error_type(client):
    c, store, db = client
    h, user = _headers(db, store, email="st@example.com")
    qid = _seed_bilingual_question(db, user).id
    # Setting error_type is reflected in the response, and omitted fields stay None.
    r = c.put(
        f"/api/practice/questions/{qid}/state",
        json={"error_type": "concept_unclear"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["error_type"] == "concept_unclear"
    assert body["is_bookmarked"] is False
    assert body["note"] is None
    # A second call with no error_type leaves the previously set value unchanged.
    r2 = c.put(
        f"/api/practice/questions/{qid}/state",
        json={"is_bookmarked": True},
        headers=h,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["error_type"] == "concept_unclear"
