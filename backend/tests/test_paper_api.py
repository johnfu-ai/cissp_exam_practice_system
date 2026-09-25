"""Papers API tests (FR-PAPER-03..07): list/detail, one-click sessions, scoring."""

import datetime as dt

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.exam import router as exam_router
from app.api.papers import router as papers_router
from app.api.practice import router as practice_router
from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.db.seed import PERMISSIONS
from app.db.session import get_session
from app.dependencies import get_lockout_store, get_refresh_store
from app.models.auth import OrganizationMembership, Role
from app.models.enums import (
    PaperStatus,
    QuestionType,
    RoleName,
)
from app.models.paper import Paper, PaperQuestion
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
    app.include_router(papers_router)
    app.include_router(practice_router)
    app.include_router(exam_router)
    store = InMemoryRefreshTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: store
    app.dependency_overrides[get_lockout_store] = lambda: InMemoryLockoutStore()
    return TestClient(app), store, db_session


def _headers(db_session, store, email="p@example.com"):
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


def _seed_choice(db_session, user, *, stem="S", correct=0):
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice,
        options=[OptionIn(order_index=0, is_correct=(correct == 0)),
                 OptionIn(order_index=1, is_correct=(correct == 1))],
        translations=[
            TranslationIn(
                language="en", stem=stem, correct_answer_rationale="r",
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
    return q


def _seed_essay(db_session, user):
    payload = QuestionCreateIn(
        question_type=QuestionType.essay, options=[],
        translations=[
            TranslationIn(language="en", stem="Explain.", correct_answer_rationale="r",
                          options=[], reference_answer="REF"),
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


def _seed_paper(db_session, user, questions, *, name="P1", scores=None,
                status=PaperStatus.published):
    scores = scores or [1] * len(questions)
    paper = Paper(
        organization_id=user.default_organization_id,
        name=name, duration_minutes=60, total_score=sum(scores),
        question_count=len(questions), status=status,
        dataset_slug="testset", paper_external_id=f"ext-{name}", domain_number=2,
    )
    paper.questions.extend([
        PaperQuestion(question_id=q.id, position=i + 1, score=s)
        for i, (q, s) in enumerate(zip(questions, scores))
    ])
    db_session.add(paper)
    db_session.flush()
    return paper


def _seed_blueprint(db_session):
    bp = ExamBlueprint(
        version_label="paper-v1", effective_date="2026-04-15",
        min_items=1, max_items=2, duration_minutes=30,
        passing_score=700, max_score=1000, is_current=True,
    )
    db_session.add(bp)
    db_session.flush()
    db_session.add(ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=100))
    db_session.flush()


def _now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def test_paper_list_and_detail(client):
    c, store, db = client
    h, user = _headers(db, store, email="p-list@example.com")
    q1 = _seed_choice(db, user, stem="PQ1")
    q2 = _seed_choice(db, user, stem="PQ2")
    _seed_essay(db, user)
    qe = db.query(Paper).filter(Paper.name == "P1").first()  # none yet
    essay_q = None
    # build paper with 2 choice + 1 essay
    from sqlalchemy import select
    from app.models.question import Question
    essay_q = db.execute(
        select(Question).where(Question.question_type == QuestionType.essay)
    ).scalars().first()
    _seed_paper(db, user, [q1, q2, essay_q], name="Mixed paper",
                scores=[2, 3, 5])
    _seed_paper(db, user, [q1], name="Draft paper", status=PaperStatus.draft)

    r = c.get("/api/papers", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    # learners see published papers only
    names = [p["name"] for p in body["items"]]
    assert names == ["Mixed paper"]
    p = body["items"][0]
    assert p["question_count"] == 3
    assert p["total_score"] == 10
    assert p["duration_minutes"] == 60
    assert p["domain_number"] == 2

    detail = c.get(f"/api/papers/{p['id']}", headers=h)
    assert detail.status_code == 200, detail.text
    d = detail.json()
    assert d["name"] == "Mixed paper"
    assert d["type_counts"] == {"single_choice": 2, "essay": 1}
    assert [q["position"] for q in d["questions"]] == [1, 2, 3]
    assert [q["score"] for q in d["questions"]] == [2, 3, 5]

    # a draft paper is 404 for learners
    draft = db.query(Paper).filter_by(name="Draft paper").one()
    assert c.get(f"/api/papers/{draft.id}", headers=h).status_code == 404


def test_paper_practice_session_flow(client):
    c, store, db = client
    h, user = _headers(db, store, email="p-prac@example.com")
    q1 = _seed_choice(db, user, stem="PP1")
    q2 = _seed_choice(db, user, stem="PP2")
    paper = _seed_paper(db, user, [q1, q2], name="Practice paper")

    r = c.post(f"/api/papers/{paper.id}/sessions",
               json={"mode": "practice"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    sid = body["id"]
    assert body["total_questions"] == 2
    assert body["config"]["paper_id"] == str(paper.id)
    # paper order preserved
    assert body["config"]["question_ids"] == [str(q1.id), str(q2.id)]

    # delivery works through the existing practice endpoints
    d = c.get(f"/api/practice/sessions/{sid}/questions/0", headers=h)
    assert d.status_code == 200
    assert d.json()["stem"]["en"] == "PP1"

    # paper sessions listing
    listing = c.get(f"/api/papers/{paper.id}/sessions", headers=h)
    assert listing.status_code == 200
    assert listing.json()["items"][0]["id"] == sid


def test_paper_exam_session_scoring(client):
    c, store, db = client
    h, user = _headers(db, store, email="p-exam@example.com")
    _seed_blueprint(db)
    q1 = _seed_choice(db, user, stem="PE1", correct=0)
    q2 = _seed_choice(db, user, stem="PE2", correct=1)
    paper = _seed_paper(db, user, [q1, q2], name="Exam paper", scores=[2, 3])

    r = c.post(f"/api/papers/{paper.id}/sessions",
               json={"mode": "exam"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    sid = body["id"]
    cfg = body["config"]
    assert cfg["paper_id"] == str(paper.id)
    assert cfg["scoring"] == "paper"
    assert cfg["max_score"] == 5
    assert cfg["passing_score"] == 3  # 60% of 5, rounded
    assert body["total_questions"] == 2
    assert cfg["duration_minutes"] == 60
    assert "deadline_at" in cfg

    # deliver + answer: q1 correct (option 0), q2 wrong (option 0; correct is 1)
    assert c.get(f"/api/exam/sessions/{sid}/questions/0", headers=h).status_code == 200
    c.post(f"/api/exam/sessions/{sid}/answers",
           json={"position": 0, "selected": [0], "started_at": _now_iso()},
           headers=h)
    c.post(f"/api/exam/sessions/{sid}/answers",
           json={"position": 1, "selected": [0], "started_at": _now_iso()},
           headers=h)

    fin = c.post(f"/api/exam/sessions/{sid}/finish", headers=h)
    assert fin.status_code == 200, fin.text
    rep = fin.json()
    # raw paper scoring: 2/5 points, 1/2 correct
    assert rep["scaled_score"] == 2
    assert rep["max_score"] == 5
    assert rep["passing_score"] == 3
    assert rep["passed"] is False
    assert rep["correct_count"] == 1
    assert rep["wrong_questions"][0]["question_id"] == str(q2.id)


def test_paper_sessions_404_cross_tenant(client, db_session, session_with_roles):
    c, store, db = client
    h, user = _headers(db, store, email="p-x@example.com")
    h2, user2 = _headers(db, store, email="p-y@example.com")
    q1 = _seed_choice(db, user, stem="PX")
    paper = _seed_paper(db, user, [q1], name="Other org paper")
    assert c.get(f"/api/papers/{paper.id}", headers=h2).status_code == 404
    assert c.post(f"/api/papers/{paper.id}/sessions",
                  json={"mode": "practice"}, headers=h2).status_code == 404


def test_essay_not_in_cat_pool(client):
    """FR-ESSAY-04: essays never enter the CAT candidate pool."""
    c, store, db = client
    h, user = _headers(db, store, email="p-cat@example.com")
    _seed_blueprint(db)
    q = _seed_essay(db, user)
    from app.models.question import QuestionMapping
    dom = db.query(ExamDomain).first()
    db.add(QuestionMapping(question_id=q.id, domain_id=dom.id))
    db.flush()
    # CAT creation must fail: pool empty (only an essay exists)
    r = c.post("/api/exam/sessions", json={"kind": "cat"}, headers=h)
    assert r.status_code == 422
