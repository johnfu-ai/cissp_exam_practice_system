"""Practice essay answering + self-assessment flow (FR-ESSAY-02)."""

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
    QuestionCreateIn,
    ReviewAction,
    TranslationIn,
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


def _headers(db_session, store, email="learner@example.com"):
    user, _ = register_user(
        db_session, email=email, password="pw12345678",
        display_name=None,
        refresh_store=store,
    )
    db_session.flush()
    r = db_session.query(Role).filter_by(name=RoleName.individual_learner).first()
    m = db_session.query(OrganizationMembership).filter_by(user_id=user.id).one()
    m.role_id = r.id
    db_session.flush()
    token = create_access_token(
        user_id=user.id, org_id=user.default_organization_id,
        roles=[RoleName.individual_learner.value],
        perms=[c for c, _ in PERMISSIONS],
    )
    return {"Authorization": f"Bearer {token}"}, user


def _seed_essay(db_session, user):
    payload = QuestionCreateIn(
        question_type=QuestionType.essay,
        options=[],
        translations=[
            TranslationIn(
                language="en", stem="Explain least privilege.",
                correct_answer_rationale="Rationale en", options=[],
                reference_answer="Minimum necessary access.",
            ),
            TranslationIn(
                language="zh", stem="解释最小特权。", correct_answer_rationale="解析zh",
                options=[], reference_answer="最小必要权限。",
            ),
        ],
    )
    q = create_question(
        db_session, org_id=user.default_organization_id, actor_id=user.id,
        payload=payload,
    )
    org_id = user.default_organization_id
    submit_review(db_session, question_id=q.id, actor_id=user.id,
                  action=ReviewAction.submit, org_id=org_id)
    submit_review(db_session, question_id=q.id, actor_id=user.id,
                  action=ReviewAction.approve, org_id=org_id)
    db_session.flush()
    return q


def _now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def test_essay_practice_flow_with_self_assessment(client):
    c, store, db = client
    h, user = _headers(db, store, email="essay-p@example.com")
    _seed_essay(db, user)

    s = c.post("/api/practice/sessions",
               json={"count": 1, "order_mode": "sequential"}, headers=h)
    assert s.status_code == 200, s.text
    sid = s.json()["id"]

    # delivery: essay => empty options, no reference answer leaked pre-answer
    d = c.get(f"/api/practice/sessions/{sid}/questions/0", headers=h)
    assert d.status_code == 200, d.text
    body = d.json()
    assert body["question_type"] == "essay"
    assert body["options"] == []
    assert "reference_answer" not in body

    # answer with free text
    a = c.post(
        f"/api/practice/sessions/{sid}/answers",
        json={"position": 0, "answer_text": "Users get only the access they need.",
              "started_at": _now_iso()},
        headers=h,
    )
    assert a.status_code == 200, a.text
    ab = a.json()
    assert ab["is_correct"] is None  # pending self-assessment
    assert ab["reference_answer"] == {
        "en": "Minimum necessary access.", "zh": "最小必要权限。"}
    assert ab["correct_indexes"] == []
    assert ab["selected_indexes"] == []

    # session summary before self-assessment: excluded from accuracy
    fin = c.post(f"/api/practice/sessions/{sid}/finish", headers=h)
    assert fin.status_code == 200, fin.text
    assert fin.json()["answered_count"] == 1
    assert fin.json()["correct_count"] == 0
    assert fin.json()["accuracy"] == 0.0  # None not counted in denominator

    # self-assess correct
    sa = c.post(f"/api/practice/sessions/{sid}/questions/0/self-assessment",
                json={"correct": True}, headers=h)
    assert sa.status_code == 200, sa.text
    assert sa.json()["is_correct"] is True

    # summary now reflects the assessment
    fin2 = c.post(f"/api/practice/sessions/{sid}/finish", headers=h)
    assert fin2.json()["correct_count"] == 1
    assert fin2.json()["accuracy"] == 1.0


def test_essay_self_assessment_wrong_increments_wrong_book(client):
    c, store, db = client
    h, user = _headers(db, store, email="essay-w@example.com")
    _seed_essay(db, user)
    s = c.post("/api/practice/sessions",
               json={"count": 1, "order_mode": "sequential"}, headers=h)
    sid = s.json()["id"]
    a = c.post(f"/api/practice/sessions/{sid}/answers",
               json={"position": 0, "answer_text": "guess",
                     "started_at": _now_iso()}, headers=h)
    assert a.status_code == 200
    sa = c.post(f"/api/practice/sessions/{sid}/questions/0/self-assessment",
                json={"correct": False}, headers=h)
    assert sa.status_code == 200

    from sqlalchemy import select
    from app.models.practice import UserQuestionState
    state = db.execute(
        select(UserQuestionState).where(UserQuestionState.user_id == user.id)
    ).scalar_one()
    assert state.wrong_count == 1
    assert state.last_wrong_at is not None


def test_essay_answer_validation(client):
    c, store, db = client
    h, user = _headers(db, store, email="essay-v@example.com")
    _seed_essay(db, user)
    s = c.post("/api/practice/sessions",
               json={"count": 1, "order_mode": "sequential"}, headers=h)
    sid = s.json()["id"]
    # empty text rejected
    bad = c.post(f"/api/practice/sessions/{sid}/answers",
                 json={"position": 0, "answer_text": "  ",
                       "started_at": _now_iso()}, headers=h)
    assert bad.status_code == 422
    # selected on an essay question rejected
    bad2 = c.post(f"/api/practice/sessions/{sid}/answers",
                  json={"position": 0, "selected": [0],
                        "started_at": _now_iso()}, headers=h)
    assert bad2.status_code == 422


def test_choice_answer_rejects_empty_selected(client):
    c, store, db = client
    h, user = _headers(db, store, email="choice-v@example.com")
    from app.schemas.question import OptionIn, TranslationOptionIn
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice,
        options=[OptionIn(order_index=0, is_correct=True),
                 OptionIn(order_index=1, is_correct=False)],
        translations=[
            TranslationIn(
                language="en", stem="Pick one.", correct_answer_rationale="r",
                options=[TranslationOptionIn(order_index=0, content="a"),
                         TranslationOptionIn(order_index=1, content="b")],
            ),
        ],
    )
    q = create_question(session=db, org_id=user.default_organization_id,
                        actor_id=user.id, payload=payload)
    org_id = user.default_organization_id
    submit_review(session=db, question_id=q.id, actor_id=user.id,
                  action=ReviewAction.submit, org_id=org_id)
    submit_review(session=db, question_id=q.id, actor_id=user.id,
                  action=ReviewAction.approve, org_id=org_id)
    db.flush()
    s = c.post("/api/practice/sessions",
               json={"count": 1, "order_mode": "sequential"}, headers=h)
    sid = s.json()["id"]
    bad = c.post(f"/api/practice/sessions/{sid}/answers",
                 json={"position": 0, "selected": [],
                       "started_at": _now_iso()}, headers=h)
    assert bad.status_code == 422


def test_self_assessment_requires_answer_first(client):
    c, store, db = client
    h, user = _headers(db, store, email="essay-o@example.com")
    _seed_essay(db, user)
    s = c.post("/api/practice/sessions",
               json={"count": 1, "order_mode": "sequential"}, headers=h)
    sid = s.json()["id"]
    sa = c.post(f"/api/practice/sessions/{sid}/questions/0/self-assessment",
                json={"correct": True}, headers=h)
    assert sa.status_code == 409
