"""Wrong-book API tests (FR-WRONG-01..05)."""

import datetime as dt

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.practice import router as practice_router
from app.api.wrong_book import router as wrong_book_router
from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.db.seed import PERMISSIONS
from app.db.session import get_session
from app.dependencies import get_lockout_store, get_refresh_store
from app.models.auth import OrganizationMembership, Role
from app.models.enums import (
    PaperStatus,
    QuestionStatus,
    QuestionType,
    RoleName,
)
from app.models.paper import Paper, PaperQuestion
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
    app.include_router(wrong_book_router)
    store = InMemoryRefreshTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: store
    app.dependency_overrides[get_lockout_store] = lambda: InMemoryLockoutStore()
    return TestClient(app), store, db_session


def _headers(db_session, store, email="wb@example.com"):
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


def _seed_choice(db_session, user, *, stem="Stem?"):
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice,
        options=[OptionIn(order_index=0, is_correct=True),
                 OptionIn(order_index=1, is_correct=False)],
        translations=[
            TranslationIn(
                language="en", stem=stem, correct_answer_rationale="why",
                options=[TranslationOptionIn(order_index=0, content="a",
                                             explanation="right"),
                         TranslationOptionIn(order_index=1, content="b",
                                             explanation="wrong")],
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


def _seed_paper(db_session, user, questions, name="Paper One"):
    paper = Paper(
        organization_id=user.default_organization_id,
        name=name, duration_minutes=60, total_score=len(questions),
        question_count=len(questions), status=PaperStatus.published,
        dataset_slug="testset", paper_external_id=f"ext-{abs(hash(name)) % 10**8}",
        domain_number=1,
    )
    paper.questions.extend([
        PaperQuestion(question_id=q.id, position=i + 1, score=1)
        for i, q in enumerate(questions)
    ])
    db_session.add(paper)
    db_session.flush()
    return paper


def _answer_wrong(c, h, sid, position=0):
    r = c.post(
        f"/api/practice/sessions/{sid}/answers",
        json={"position": position, "selected": [1],
              "started_at": dt.datetime.now(dt.timezone.utc).isoformat()},
        headers=h,
    )
    assert r.status_code == 200, r.text


def _answer_right(c, h, sid, position=0):
    r = c.post(
        f"/api/practice/sessions/{sid}/answers",
        json={"position": position, "selected": [0],
              "started_at": dt.datetime.now(dt.timezone.utc).isoformat()},
        headers=h,
    )
    assert r.status_code == 200, r.text


def test_wrong_book_lists_wrong_counts_and_papers(client):
    c, store, db = client
    h, user = _headers(db, store, email="wb1@example.com")
    q1 = _seed_choice(db, user, stem="Q1")
    q2 = _seed_choice(db, user, stem="Q2")
    paper = _seed_paper(db, user, [q1, q2])

    s = c.post("/api/practice/sessions",
               json={"count": 2, "order_mode": "sequential"}, headers=h)
    sid = s.json()["id"]
    _answer_wrong(c, h, sid, position=0)
    _answer_wrong(c, h, sid, position=1)
    # wrong twice on q1 via a second session (resolve q1's real position)
    s2 = c.post("/api/practice/sessions",
                json={"count": 2, "order_mode": "sequential"}, headers=h)
    pos_q1 = s2.json()["config"]["question_ids"].index(str(q1.id))
    _answer_wrong(c, h, s2.json()["id"], position=pos_q1)

    r = c.get("/api/wrong-book", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2
    items = {i["question_id"]: i for i in body["items"]}
    assert items[str(q1.id)]["wrong_count"] == 2
    assert items[str(q2.id)]["wrong_count"] == 1
    assert paper.name in items[str(q1.id)]["papers"]
    assert items[str(q1.id)]["question_type"] == "single_choice"
    assert items[str(q1.id)]["stem"]["en"] == "Q1"
    assert items[str(q1.id)]["is_mastered"] is False
    # most recent wrong first (q1 was last wrong)
    assert body["items"][0]["question_id"] == str(q1.id)


def test_wrong_book_tabs_and_filters(client):
    c, store, db = client
    h, user = _headers(db, store, email="wb2@example.com")
    q1 = _seed_choice(db, user, stem="QB1")
    q2 = _seed_choice(db, user, stem="QB2")
    _seed_paper(db, user, [q1], name="Only Q1 paper")

    s = c.post("/api/practice/sessions",
               json={"count": 2, "order_mode": "sequential"}, headers=h)
    sid = s.json()["id"]
    # created_at has second precision -> resolve real positions from config
    qids = s.json()["config"]["question_ids"]
    pos_q1, pos_q2 = qids.index(str(q1.id)), qids.index(str(q2.id))
    _answer_wrong(c, h, sid, position=pos_q1)   # q1 wrong (in paper)
    _answer_right(c, h, sid, position=pos_q2)   # q2 right, then bookmark it

    c.put(f"/api/practice/questions/{q2.id}/state",
          json={"is_bookmarked": True}, headers=h)
    c.put(f"/api/practice/questions/{q1.id}/state",
          json={"is_flagged_review": True}, headers=h)

    # tab=wrong
    wrong = c.get("/api/wrong-book?tab=wrong", headers=h).json()
    assert [i["question_id"] for i in wrong["items"]] == [str(q1.id)]
    # tab=bookmarked
    bm = c.get("/api/wrong-book?tab=bookmarked", headers=h).json()
    assert [i["question_id"] for i in bm["items"]] == [str(q2.id)]
    # tab=flagged
    fl = c.get("/api/wrong-book?tab=flagged", headers=h).json()
    assert [i["question_id"] for i in fl["items"]] == [str(q1.id)]
    # paper filter on the wrong tab
    paper = db.query(Paper).filter_by(name="Only Q1 paper").one()
    pfiltered = c.get(f"/api/wrong-book?tab=wrong&paper_id={paper.id}",
                      headers=h).json()
    assert [i["question_id"] for i in pfiltered["items"]] == [str(q1.id)]
    other_paper = _seed_paper(db, user, [q2], name="Q2 paper")
    empty = c.get(f"/api/wrong-book?tab=wrong&paper_id={other_paper.id}",
                  headers=h).json()
    assert empty["items"] == []


def test_wrong_book_mastered_moves_out_of_wrong_tab(client):
    c, store, db = client
    h, user = _headers(db, store, email="wb3@example.com")
    q1 = _seed_choice(db, user, stem="QM")
    s = c.post("/api/practice/sessions",
               json={"count": 1, "order_mode": "sequential"}, headers=h)
    _answer_wrong(c, h, s.json()["id"], position=0)

    c.put(f"/api/practice/questions/{q1.id}/state",
          json={"is_mastered": True}, headers=h)
    wrong = c.get("/api/wrong-book?tab=wrong", headers=h).json()
    assert wrong["items"] == []
    # history preserved: wrong_count still visible via all tab? (spec: count
    # not cleared, only status changes — wrong tab excludes mastered)
    from sqlalchemy import select
    from app.models.practice import UserQuestionState
    state = db.execute(
        select(UserQuestionState).where(UserQuestionState.user_id == user.id)
    ).scalar_one()
    assert state.wrong_count == 1


def test_wrong_book_repractice_and_recovery(client):
    c, store, db = client
    h, user = _headers(db, store, email="wb4@example.com")
    q1 = _seed_choice(db, user, stem="QR")
    _seed_paper(db, user, [q1], name="R paper")
    s = c.post("/api/practice/sessions",
               json={"count": 1, "order_mode": "sequential"}, headers=h)
    _answer_wrong(c, h, s.json()["id"], position=0)

    # re-practice from the wrong book
    rp = c.post("/api/wrong-book/practice", json={"count": 10}, headers=h)
    assert rp.status_code == 200, rp.text
    sid = rp.json()["id"]
    assert rp.json()["total_questions"] == 1
    assert rp.json()["config"]["subset"] == "wrong"
    # answer correctly this time -> mastery promoted, still in wrong tab until
    # mastered? FR-WRONG-05: re-practice correct promotes mastery level.
    _answer_right(c, h, sid, position=0)
    from sqlalchemy import select
    from app.models.practice import UserQuestionState, MasteryLevel
    state = db.execute(
        select(UserQuestionState).where(UserQuestionState.user_id == user.id)
    ).scalar_one()
    assert state.mastery_level == MasteryLevel.mastered
    assert state.wrong_count == 1  # cumulative history kept


def test_wrong_book_repractice_with_paper_filter(client):
    c, store, db = client
    h, user = _headers(db, store, email="wb5@example.com")
    q1 = _seed_choice(db, user, stem="QF1")
    q2 = _seed_choice(db, user, stem="QF2")
    _seed_paper(db, user, [q1], name="F1 paper")
    s = c.post("/api/practice/sessions",
               json={"count": 2, "order_mode": "sequential"}, headers=h)
    sid = s.json()["id"]
    _answer_wrong(c, h, sid, position=0)
    _answer_wrong(c, h, sid, position=1)

    paper = db.query(Paper).filter_by(name="F1 paper").one()
    rp = c.post("/api/wrong-book/practice",
                json={"count": 10, "paper_id": str(paper.id)}, headers=h)
    assert rp.status_code == 200, rp.text
    assert rp.json()["total_questions"] == 1
