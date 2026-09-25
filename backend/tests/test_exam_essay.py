"""Exam essay answering + post-finish self-assessment (FR-ESSAY-03)."""

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
from app.models.taxonomy import ExamBlueprint, ExamDomain
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
    from app.api.papers import router as papers_router
    app.include_router(papers_router)
    store = InMemoryRefreshTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: store
    app.dependency_overrides[get_lockout_store] = lambda: InMemoryLockoutStore()
    return TestClient(app), store, db_session


def _headers(db_session, store, email="exam@example.com"):
    user, _ = register_user(
        db_session, email=email, password="pw12345678", display_name=None, refresh_store=store,
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


def _seed_blueprint(db_session):
    bp = ExamBlueprint(
        version_label="essay-v1", effective_date="2026-04-15",
        min_items=1, max_items=2, duration_minutes=30,
        passing_score=700, max_score=1000, is_current=True,
    )
    db_session.add(bp)
    db_session.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=100)
    db_session.add(dom)
    db_session.flush()
    return bp, dom


def _seed_question(db_session, user, domain, q_type, reference=None):
    if q_type is QuestionType.essay:
        payload = QuestionCreateIn(
            question_type=q_type, options=[],
            translations=[
                TranslationIn(language="en", stem="Explain X.",
                              correct_answer_rationale="r", options=[],
                              reference_answer=reference or "Reference answer."),
            ],
        )
    else:
        payload = QuestionCreateIn(
            question_type=q_type,
            options=[OptionIn(order_index=0, is_correct=True),
                     OptionIn(order_index=1, is_correct=False)],
            translations=[
                TranslationIn(
                    language="en", stem="Pick.", correct_answer_rationale="r",
                    options=[TranslationOptionIn(order_index=0, content="a"),
                             TranslationOptionIn(order_index=1, content="b")],
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
    if domain is not None:
        from app.models.question import QuestionMapping
        db_session.add(QuestionMapping(question_id=q.id, domain_id=domain.id))
        db_session.flush()
    return q


def _seed_paper(db_session, user, questions, *, name="Essay paper"):
    from app.models.enums import PaperStatus
    from app.models.paper import Paper, PaperQuestion
    paper = Paper(
        organization_id=user.default_organization_id,
        name=name, duration_minutes=60, total_score=len(questions),
        question_count=len(questions), status=PaperStatus.published,
        dataset_slug="testset", paper_external_id=f"ext-{name}",
    )
    paper.questions.extend([
        PaperQuestion(question_id=q.id, position=i + 1, score=1)
        for i, q in enumerate(questions)
    ])
    db_session.add(paper)
    db_session.flush()
    return paper


def _now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def test_exam_essay_records_text_then_self_assess_after_finish(client):
    c, store, db = client
    h, user = _headers(db, store, email="exam-essay@example.com")
    # FR-ESSAY-04: essays only reach exams through PAPER sessions
    _seed_blueprint(db)
    q = _seed_question(db, user, None, QuestionType.essay)
    paper = _seed_paper(db, user, [q])

    s = c.post(f"/api/papers/{paper.id}/sessions",
               json={"mode": "exam"}, headers=h)
    assert s.status_code == 200, s.text
    sid = s.json()["id"]

    d = c.get(f"/api/exam/sessions/{sid}/questions/0", headers=h)
    body = d.json()
    assert body["question_type"] == "essay"
    assert body["options"] == []
    assert "reference_answer" not in body  # not leaked during exam

    a = c.post(f"/api/exam/sessions/{sid}/answers",
               json={"position": 0, "answer_text": "my answer",
                     "started_at": _now_iso()}, headers=h)
    assert a.status_code == 200, a.text
    assert a.json()["saved"] is True

    # self-assessment rejected while the session is in progress
    early = c.post(f"/api/exam/sessions/{sid}/answers/0/self-assessment",
                   json={"correct": True}, headers=h)
    assert early.status_code == 409

    fin = c.post(f"/api/exam/sessions/{sid}/finish", headers=h)
    assert fin.status_code == 200, fin.text
    rep = fin.json()
    assert rep["correct_count"] == 0  # unassessed essay is not correct

    # review shows the reference answer + the text
    rev = c.get(f"/api/exam/sessions/{sid}/review", headers=h)
    assert rev.status_code == 200, rev.text
    item = rev.json()[0]
    assert item["question_type"] == "essay"
    assert item["reference_answer"] == {"en": "Reference answer.", "zh": None}
    assert item["your_answer"]["text"] == "my answer"
    assert item["your_answer"]["is_correct"] is None

    # self-assess correct -> report recomputes on read
    sa = c.post(f"/api/exam/sessions/{sid}/answers/0/self-assessment",
                json={"correct": True}, headers=h)
    assert sa.status_code == 200, sa.text
    rep2 = c.get(f"/api/exam/sessions/{sid}/report", headers=h).json()
    assert rep2["correct_count"] == 1


def test_exam_essay_wrong_self_assessment_hits_wrong_book(client):
    c, store, db = client
    h, user = _headers(db, store, email="exam-essay-w@example.com")
    _seed_blueprint(db)
    q = _seed_question(db, user, None, QuestionType.essay)
    paper = _seed_paper(db, user, [q], name="Essay paper 2")
    s = c.post(f"/api/papers/{paper.id}/sessions",
               json={"mode": "exam"}, headers=h)
    sid = s.json()["id"]
    c.post(f"/api/exam/sessions/{sid}/answers",
           json={"position": 0, "answer_text": "nope", "started_at": _now_iso()},
           headers=h)
    c.post(f"/api/exam/sessions/{sid}/finish", headers=h)
    sa = c.post(f"/api/exam/sessions/{sid}/answers/0/self-assessment",
                json={"correct": False}, headers=h)
    assert sa.status_code == 200

    from sqlalchemy import select
    from app.models.practice import UserQuestionState
    state = db.execute(
        select(UserQuestionState).where(UserQuestionState.user_id == user.id)
    ).scalar_one()
    assert state.wrong_count == 1


def test_exam_choice_wrong_answer_increments_wrong_book_on_finish(client):
    c, store, db = client
    h, user = _headers(db, store, email="exam-choice-w@example.com")
    _seed_blueprint(db)
    from app.models.taxonomy import ExamDomain
    dom = db.query(ExamDomain).first()
    _seed_question(db, user, dom, QuestionType.single_choice)
    s = c.post("/api/exam/sessions", json={"count": 1}, headers=h)
    sid = s.json()["id"]
    # answer wrong (correct is option 0; pick 1)
    c.post(f"/api/exam/sessions/{sid}/answers",
           json={"position": 0, "selected": [1], "started_at": _now_iso()},
           headers=h)
    c.post(f"/api/exam/sessions/{sid}/finish", headers=h)

    from sqlalchemy import select
    from app.models.practice import UserQuestionState
    state = db.execute(
        select(UserQuestionState).where(UserQuestionState.user_id == user.id)
    ).scalar_one()
    assert state.wrong_count == 1
    assert state.last_wrong_at is not None
