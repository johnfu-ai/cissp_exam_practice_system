"""PRD v1.5 FR-PAPER-10..13 tests: free-practice banks, resume bundle +
heartbeat, practice⇄exam mode switch, previous-answer essay text."""

import datetime as dt
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.exam import router as exam_router
from app.api.papers import banks_router
from app.api.papers import router as papers_router
from app.api.practice import router as practice_router
from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.db.seed import PERMISSIONS
from app.db.session import get_session
from app.dependencies import get_lockout_store, get_refresh_store
from app.models.auth import OrganizationMembership, Role
from app.models.enums import (
    ImportFormat,
    PaperStatus,
    QuestionType,
    RoleName,
)
from app.models.etl import EtlDataset, QuestionExternalKey
from app.models.exam import ExamAnswer, ExamSession
from app.models.paper import Paper, PaperQuestion
from app.models.practice import PracticeAnswer, PracticeSession
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
    app.include_router(banks_router)
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
        db_session, email=email, password="pw12345678", display_name=None,
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


def _seed_essay(db_session, user, *, stem="Explain."):
    payload = QuestionCreateIn(
        question_type=QuestionType.essay, options=[],
        translations=[
            TranslationIn(language="en", stem=stem, correct_answer_rationale="r",
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


def _seed_dataset(db_session, user, slug, name, questions, *, with_paper=False,
                  duration=30, scores=None):
    """Register a dataset + external keys over `questions` (optionally a paper)."""
    ds = EtlDataset(
        organization_id=user.default_organization_id, slug=slug, name=name,
        source_path=f"docs/questions/{slug}", format=ImportFormat.json,
        total_questions=len(questions), languages=["en"],
    )
    db_session.add(ds)
    for i, q in enumerate(questions):
        db_session.add(QuestionExternalKey(
            dataset_slug=slug, external_id=f"{slug}-{i}", question_id=q.id,
        ))
    db_session.flush()
    if with_paper:
        _seed_paper(db_session, user, questions, name=f"{slug} paper",
                    scores=scores, dataset_slug=slug, duration=duration)
    return ds


def _seed_paper(db_session, user, questions, *, name="P1", scores=None,
                status=PaperStatus.published, dataset_slug="testset",
                duration=30):
    scores = scores or [1] * len(questions)
    paper = Paper(
        organization_id=user.default_organization_id,
        name=name, duration_minutes=duration, total_score=sum(scores),
        question_count=len(questions), status=status,
        dataset_slug=dataset_slug, paper_external_id=f"ext-{name}-{uuid.uuid4()}",
        domain_number=2,
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


def _start_practice(client, h, paper, mode="practice"):
    c, _, _ = client
    return c.post(f"/api/papers/{paper.id}/sessions", json={"mode": mode},
                  headers=h)


# --- FR-PAPER-10: banks --------------------------------------------------------


def test_banks_lists_datasets_with_published_counts(client):
    c, store, db = client
    h, user = _headers(db, store, email="banks@example.com")
    osg_q = [_seed_choice(db, user, stem=f"O{i}") for i in range(3)]
    # one draft question (never approved) must not count toward the bank
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice,
        options=[OptionIn(order_index=0, is_correct=True),
                 OptionIn(order_index=1, is_correct=False)],
        translations=[
            TranslationIn(
                language="en", stem="draft q", correct_answer_rationale="r",
                options=[TranslationOptionIn(order_index=0, content="a"),
                         TranslationOptionIn(order_index=1, content="b")],
            ),
        ],
    )
    draft_q = create_question(
        db, org_id=user.default_organization_id, actor_id=user.id, payload=payload,
    )
    db.flush()
    _seed_dataset(db, user, "osg10", "CISSP OSG v10", osg_q + [draft_q])
    # paper-like dataset: questions exist but stay draft; papers cover it
    gq = [_seed_choice(db, user, stem=f"G{i}") for i in range(2)]
    _seed_dataset(db, user, "mockpapers", "Mock papers", gq, with_paper=True)
    # empty dataset is excluded entirely
    _seed_dataset(db, user, "empty", "Empty", [])

    r = c.get("/api/banks", headers=h)
    assert r.status_code == 200, r.text
    items = {b["dataset_slug"]: b for b in r.json()["items"]}
    assert set(items) == {"osg10", "mockpapers"}
    assert items["osg10"]["question_count"] == 3
    assert items["osg10"]["has_papers"] is False
    assert items["osg10"]["name"] == "CISSP OSG v10"
    assert items["mockpapers"]["has_papers"] is True


def test_practice_session_dataset_scoping(client):
    c, store, db = client
    h, user = _headers(db, store, email="scope@example.com")
    osg_q = [_seed_choice(db, user, stem=f"O{i}") for i in range(3)]
    other_q = [_seed_choice(db, user, stem=f"X{i}") for i in range(2)]
    _seed_dataset(db, user, "osg10", "CISSP OSG v10", osg_q)
    _seed_dataset(db, user, "other", "Other", other_q)

    r = c.post("/api/practice/sessions", headers=h, json={
        "dataset_slug": "osg10", "count": 10, "order_mode": "sequential",
    })
    assert r.status_code == 200, r.text
    cfg = r.json()["config"]
    assert len(cfg["question_ids"]) == 3
    assert set(cfg["question_ids"]) == {str(q.id) for q in osg_q}
    assert cfg["dataset_slug"] == "osg10"

    # unknown dataset -> no questions match
    r = c.post("/api/practice/sessions", headers=h, json={
        "dataset_slug": "nope", "count": 10,
    })
    assert r.status_code == 422


# --- FR-PAPER-12: heartbeat + elapsed ------------------------------------------


def test_heartbeat_accumulates_and_clamps(client):
    c, store, db = client
    h, user = _headers(db, store, email="hb@example.com")
    qs = [_seed_choice(db, user, stem=f"H{i}") for i in range(2)]
    paper = _seed_paper(db, user, qs, name="HB paper")
    sid = _start_practice(client, h, paper).json()["id"]

    r = c.post(f"/api/practice/sessions/{sid}/heartbeat",
               json={"elapsed_seconds": 30}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["elapsed_seconds"] == 30

    # a single report may not jump more than 300s ahead
    r = c.post(f"/api/practice/sessions/{sid}/heartbeat",
               json={"elapsed_seconds": 600}, headers=h)
    assert r.json()["elapsed_seconds"] == 330

    # monotonic: reporting less never decreases it
    r = c.post(f"/api/practice/sessions/{sid}/heartbeat",
               json={"elapsed_seconds": 100}, headers=h)
    assert r.json()["elapsed_seconds"] == 330

    # delivery carries the accumulated elapsed
    d = c.get(f"/api/practice/sessions/{sid}/questions/0", headers=h).json()
    assert 330_000 <= d["elapsed_ms"] <= 330_000 + 120_000


def test_heartbeat_away_time_not_counted(client):
    c, store, db = client
    h, user = _headers(db, store, email="away@example.com")
    qs = [_seed_choice(db, user, stem=f"A{i}") for i in range(2)]
    paper = _seed_paper(db, user, qs, name="Away paper")
    sid = _start_practice(client, h, paper).json()["id"]
    c.post(f"/api/practice/sessions/{sid}/heartbeat",
           json={"elapsed_seconds": 30}, headers=h)

    # simulate the player being closed for an hour
    from sqlalchemy.orm.attributes import flag_modified
    ps = db.get(PracticeSession, uuid.UUID(sid))
    ps.config["last_seen_at"] = (
        dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    ).isoformat()
    flag_modified(ps, "config")
    db.flush()

    d = c.get(f"/api/practice/sessions/{sid}/questions/0", headers=h).json()
    assert 30_000 <= d["elapsed_ms"] <= 45_000


def test_heartbeat_rejects_finished_session(client):
    c, store, db = client
    h, user = _headers(db, store, email="hbf@example.com")
    qs = [_seed_choice(db, user, stem=f"HF{i}") for i in range(2)]
    paper = _seed_paper(db, user, qs, name="HBF paper")
    sid = _start_practice(client, h, paper).json()["id"]
    assert c.post(f"/api/practice/sessions/{sid}/finish", headers=h).status_code == 200
    r = c.post(f"/api/practice/sessions/{sid}/heartbeat",
               json={"elapsed_seconds": 30}, headers=h)
    assert r.status_code == 409


def test_delivery_elapsed_legacy_wallclock(client):
    c, store, db = client
    h, user = _headers(db, store, email="leg@example.com")
    qs = [_seed_choice(db, user, stem=f"L{i}") for i in range(2)]
    paper = _seed_paper(db, user, qs, name="Legacy paper")
    sid = _start_practice(client, h, paper).json()["id"]
    # no heartbeat ever: elapsed follows the wall clock since start
    d = c.get(f"/api/practice/sessions/{sid}/questions/0", headers=h).json()
    assert 0 <= d["elapsed_ms"] < 60_000


# --- FR-PAPER-12: resume state ---------------------------------------------------


def test_state_practice_session(client):
    c, store, db = client
    h, user = _headers(db, store, email="st-p@example.com")
    q1 = _seed_choice(db, user, stem="ST1", correct=0)
    q2 = _seed_choice(db, user, stem="ST2", correct=1)  # user will pick wrong
    q3 = _seed_choice(db, user, stem="ST3")
    paper = _seed_paper(db, user, [q1, q2, q3], name="State paper")
    sid = _start_practice(client, h, paper).json()["id"]
    c.post(f"/api/practice/sessions/{sid}/heartbeat",
           json={"elapsed_seconds": 42}, headers=h)
    # answer pos0 correctly, pos1 incorrectly, leave pos2 unanswered
    c.post(f"/api/practice/sessions/{sid}/answers", headers=h, json={
        "position": 0, "selected": [0], "started_at": _now_iso(),
    })
    c.post(f"/api/practice/sessions/{sid}/answers", headers=h, json={
        "position": 1, "selected": [0], "started_at": _now_iso(),
    })

    r = c.get(f"/api/papers/sessions/{sid}/state", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "practice"
    assert body["status"] == "in_progress"
    assert body["paper_id"] == str(paper.id)
    assert body["paper_name"] == "State paper"
    assert body["total"] == 3
    assert body["answered_positions"] == [0, 1]
    assert body["wrong_positions"] == [1]
    assert 42 <= body["elapsed_seconds"] <= 162
    assert body["deadline_at"] is None


def test_state_exam_session_hides_correctness(client):
    c, store, db = client
    h, user = _headers(db, store, email="st-e@example.com")
    _seed_blueprint(db)
    q1 = _seed_choice(db, user, stem="SE1", correct=0)
    q2 = _seed_choice(db, user, stem="SE2", correct=1)
    paper = _seed_paper(db, user, [q1, q2], name="State exam paper")
    sid = _start_practice(client, h, paper, mode="exam").json()["id"]
    c.post(f"/api/exam/sessions/{sid}/answers", headers=h, json={
        "position": 0, "selected": [0], "started_at": _now_iso(),
    })
    c.post(f"/api/exam/sessions/{sid}/answers", headers=h, json={
        "position": 1, "selected": [0], "started_at": _now_iso(),  # wrong
    })

    r = c.get(f"/api/papers/sessions/{sid}/state", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "exam"
    assert body["answered_positions"] == [0, 1]
    # exam mode never leaks correctness to the answer sheet
    assert body["wrong_positions"] == []
    assert body["deadline_at"] is not None
    assert body["elapsed_seconds"] is None


def test_state_bank_practice_session(client):
    c, store, db = client
    h, user = _headers(db, store, email="st-b@example.com")
    qs = [_seed_choice(db, user, stem=f"B{i}") for i in range(2)]
    _seed_dataset(db, user, "osg10", "CISSP OSG v10", qs)
    sid = c.post("/api/practice/sessions", headers=h, json={
        "dataset_slug": "osg10", "count": 10, "order_mode": "sequential",
    }).json()["id"]

    r = c.get(f"/api/papers/sessions/{sid}/state", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "practice"
    assert body["paper_id"] is None
    assert body["paper_name"] is None
    assert body["total"] == 2


def test_state_cross_user_and_unknown_404(client):
    c, store, db = client
    h, user = _headers(db, store, email="st-x@example.com")
    h2, user2 = _headers(db, store, email="st-y@example.com")
    qs = [_seed_choice(db, user, stem=f"X{i}") for i in range(2)]
    paper = _seed_paper(db, user, qs, name="X paper")
    sid = _start_practice(client, h, paper).json()["id"]
    assert c.get(f"/api/papers/sessions/{sid}/state", headers=h2).status_code == 404
    assert c.get(
        "/api/papers/sessions/00000000-0000-0000-0000-000000000000/state",
        headers=h,
    ).status_code == 404


def test_previous_answer_carries_essay_text(client):
    c, store, db = client
    h, user = _headers(db, store, email="essay@example.com")
    _seed_blueprint(db)
    q1 = _seed_choice(db, user, stem="E1")
    essay = _seed_essay(db, user)
    paper = _seed_paper(db, user, [q1, essay], name="Essay paper", scores=[2, 5])

    # practice: submit essay text, re-read delivery
    sid = _start_practice(client, h, paper).json()["id"]
    c.post(f"/api/practice/sessions/{sid}/answers", headers=h, json={
        "position": 1, "answer_text": "MY PRACTICE ESSAY", "started_at": _now_iso(),
    })
    d = c.get(f"/api/practice/sessions/{sid}/questions/1", headers=h).json()
    assert d["previous_answer"]["text"] == "MY PRACTICE ESSAY"

    # exam: save essay answer, re-read delivery
    sid2 = _start_practice(client, h, paper, mode="exam").json()["id"]
    c.post(f"/api/exam/sessions/{sid2}/answers", headers=h, json={
        "position": 1, "answer_text": "MY EXAM ESSAY", "started_at": _now_iso(),
    })
    d2 = c.get(f"/api/exam/sessions/{sid2}/questions/1", headers=h).json()
    assert d2["previous_answer"]["text"] == "MY EXAM ESSAY"


# --- FR-PAPER-12: in-progress listing -------------------------------------------


def test_in_progress_lists_paper_and_bank_sessions(client):
    c, store, db = client
    h, user = _headers(db, store, email="ip@example.com")
    h2, user2 = _headers(db, store, email="ip2@example.com")
    _seed_blueprint(db)
    qs = [_seed_choice(db, user, stem=f"IP{i}") for i in range(3)]
    paper = _seed_paper(db, user, qs, name="IP paper")
    bank_qs = [_seed_choice(db, user, stem=f"BNK{i}") for i in range(2)]
    _seed_dataset(db, user, "osg10", "CISSP OSG v10", bank_qs)

    ps = _start_practice(client, h, paper).json()["id"]
    es = _start_practice(client, h, paper, mode="exam").json()["id"]
    bs = c.post("/api/practice/sessions", headers=h, json={
        "dataset_slug": "osg10", "count": 10,
    }).json()["id"]
    finished = _start_practice(client, h, paper).json()["id"]
    c.post(f"/api/practice/sessions/{finished}/finish", headers=h)
    plain = c.post("/api/practice/sessions", headers=h, json={
        "count": 10,
    }).json()["id"]  # neither paper nor bank -> excluded

    r = c.get("/api/papers/sessions/in-progress", headers=h)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    ids = [i["session_id"] for i in items]
    assert set(ids) == {ps, es, bs}
    assert finished not in ids and plain not in ids
    by_id = {i["session_id"]: i for i in items}
    assert by_id[ps]["kind"] == "practice"
    assert by_id[ps]["source"] == "paper"
    assert by_id[ps]["paper_id"] == str(paper.id)
    assert by_id[ps]["paper_name"] == "IP paper"
    assert by_id[es]["kind"] == "exam"
    assert by_id[bs]["source"] == "bank"
    assert by_id[bs]["dataset_slug"] == "osg10"
    assert by_id[bs]["dataset_name"] == "CISSP OSG v10"

    # another user sees nothing
    assert c.get("/api/papers/sessions/in-progress", headers=h2).json()["items"] == []


# --- FR-PAPER-14: 做题记录 (attempt history with stats) ---------------------------


def test_paper_sessions_carry_attempt_stats(client):
    """GET /api/papers/{id}/sessions items carry answered/score/max_score/
    passed/duration_seconds for the attempt-history modal (FR-PAPER-14)."""
    c, store, db = client
    h, user = _headers(db, store, email="records@example.com")
    _seed_blueprint(db)
    q1 = _seed_choice(db, user, stem="R1", correct=0)
    q2 = _seed_choice(db, user, stem="R2", correct=1)
    paper = _seed_paper(db, user, [q1, q2], name="REC", scores=[2, 3])

    # exam: q1 right (2 points), q2 wrong (0) -> 2/5, below the 60% line (3)
    sid = _start_practice(client, h, paper, mode="exam").json()["id"]
    c.post(f"/api/exam/sessions/{sid}/answers",
           json={"position": 0, "selected": [0], "started_at": _now_iso()},
           headers=h)
    c.post(f"/api/exam/sessions/{sid}/answers",
           json={"position": 1, "selected": [0], "started_at": _now_iso()},
           headers=h)
    fin = c.post(f"/api/exam/sessions/{sid}/finish", headers=h)
    assert fin.status_code == 200, fin.text

    # practice: in progress with one answer (no score concept)
    pid = _start_practice(client, h, paper).json()["id"]
    c.post(f"/api/practice/sessions/{pid}/answers",
           json={"position": 0, "selected": [0], "started_at": _now_iso()},
           headers=h)

    r = c.get(f"/api/papers/{paper.id}/sessions", headers=h)
    assert r.status_code == 200, r.text
    by_id = {it["id"]: it for it in r.json()["items"]}
    ex = by_id[sid]
    assert ex["kind"] == "exam"
    assert ex["answered"] == 2
    assert ex["score"] == 2
    assert ex["max_score"] == 5
    assert ex["passed"] is False
    assert isinstance(ex["duration_seconds"], int)
    assert ex["duration_seconds"] >= 0
    pr = by_id[pid]
    assert pr["kind"] == "practice"
    assert pr["answered"] == 1
    assert pr["score"] is None
    assert pr["max_score"] is None
    assert pr["passed"] is None


def test_paper_sessions_passing_exam_scores_pass(client):
    """A passing paper exam reports passed=True with the raw point score."""
    c, store, db = client
    h, user = _headers(db, store, email="pass@example.com")
    _seed_blueprint(db)
    q1 = _seed_choice(db, user, stem="PS1", correct=0)
    q2 = _seed_choice(db, user, stem="PS2", correct=0)
    paper = _seed_paper(db, user, [q1, q2], name="PASS", scores=[2, 3])

    sid = _start_practice(client, h, paper, mode="exam").json()["id"]
    for pos in (0, 1):
        c.post(f"/api/exam/sessions/{sid}/answers",
               json={"position": pos, "selected": [0], "started_at": _now_iso()},
               headers=h)
    c.post(f"/api/exam/sessions/{sid}/finish", headers=h)

    items = c.get(f"/api/papers/{paper.id}/sessions", headers=h).json()["items"]
    ex = next(it for it in items if it["id"] == sid)
    assert ex["score"] == 5
    assert ex["passed"] is True


# --- FR-PAPER-11: mode switch ----------------------------------------------------


def test_switch_practice_to_exam(client):
    c, store, db = client
    h, user = _headers(db, store, email="sw-pe@example.com")
    _seed_blueprint(db)
    q1 = _seed_choice(db, user, stem="SW1", correct=0)
    q2 = _seed_choice(db, user, stem="SW2", correct=1)
    essay = _seed_essay(db, user)
    paper = _seed_paper(db, user, [q1, q2, essay], name="SW paper",
                        scores=[2, 3, 5], duration=30)
    sid = _start_practice(client, h, paper).json()["id"]
    # answer pos0 correctly; essay pos2 + self-assess right; 10 minutes elapsed
    c.post(f"/api/practice/sessions/{sid}/answers", headers=h, json={
        "position": 0, "selected": [0], "started_at": _now_iso(),
    })
    c.post(f"/api/practice/sessions/{sid}/answers", headers=h, json={
        "position": 2, "answer_text": "essay text", "started_at": _now_iso(),
    })
    c.post(f"/api/practice/sessions/{sid}/questions/2/self-assessment",
           json={"correct": True}, headers=h)
    # accumulate 10 minutes of practice time (300s max step per heartbeat)
    for _ in range(2):
        c.post(f"/api/practice/sessions/{sid}/heartbeat",
               json={"elapsed_seconds": 600}, headers=h)

    r = c.post(f"/api/papers/sessions/{sid}/switch-mode",
               json={"mode": "exam"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    new_id = body["session_id"]
    assert body["kind"] == "exam"
    assert body["paper_id"] == str(paper.id)
    assert new_id != sid

    # old practice session abandoned
    old = db.get(PracticeSession, uuid.UUID(sid))
    assert old.status.value == "abandoned"

    es = db.get(ExamSession, uuid.UUID(new_id))
    assert es.status.value == "in_progress"
    assert es.config["scoring"] == "paper"
    assert es.config["question_ids"] == [str(q1.id), str(q2.id), str(essay.id)]
    assert es.config["scores"] == [2, 3, 5]
    # deadline honors 30min duration minus 10min elapsed
    deadline = dt.datetime.fromisoformat(es.config["deadline_at"])
    remaining = (deadline - dt.datetime.now(dt.timezone.utc)).total_seconds()
    assert 1100 <= remaining <= 1200 + 60
    # answers carried over with correctness + essay self-assessment
    answers = {
        a.question_id: a for a in db.execute(
            select(ExamAnswer).where(ExamAnswer.session_id == es.id)
        ).scalars().all()
    }
    assert answers[q1.id].is_correct is True
    assert answers[essay.id].is_correct is True
    assert answers[essay.id].user_answer == {"text": "essay text"}
    assert q2.id not in answers

    # delivery via the exam API works and previous answers are visible
    d = c.get(f"/api/exam/sessions/{new_id}/questions/0", headers=h)
    assert d.status_code == 200
    assert d.json()["previous_answer"]["selected"] == [0]

    # audit row for the switch
    from app.models.admin import AuditLog
    row = db.execute(
        select(AuditLog).where(
            AuditLog.entity_id == str(es.id),
            AuditLog.entity_type == "exam_session",
        )
    ).scalars().first()
    assert row is not None
    assert row.details["switched_from"] == sid


def test_switch_practice_to_exam_time_exhausted(client):
    c, store, db = client
    h, user = _headers(db, store, email="sw-t@example.com")
    qs = [_seed_choice(db, user, stem=f"TX{i}") for i in range(2)]
    paper = _seed_paper(db, user, qs, name="TX paper", duration=30)
    sid = _start_practice(client, h, paper).json()["id"]
    # exhaust the clock across several heartbeats (300s max step each)
    for _ in range(7):
        c.post(f"/api/practice/sessions/{sid}/heartbeat",
               json={"elapsed_seconds": 10_000}, headers=h)
    r = c.post(f"/api/papers/sessions/{sid}/switch-mode",
               json={"mode": "exam"}, headers=h)
    assert r.status_code == 422


def test_switch_exam_to_practice(client):
    c, store, db = client
    h, user = _headers(db, store, email="sw-ep@example.com")
    _seed_blueprint(db)
    q1 = _seed_choice(db, user, stem="EP1", correct=0)
    q2 = _seed_choice(db, user, stem="EP2", correct=1)
    essay = _seed_essay(db, user)
    paper = _seed_paper(db, user, [q1, q2, essay], name="EP paper",
                        scores=[2, 3, 5], duration=30)
    sid = _start_practice(client, h, paper, mode="exam").json()["id"]
    c.post(f"/api/exam/sessions/{sid}/answers", headers=h, json={
        "position": 0, "selected": [0], "started_at": _now_iso(),   # correct
    })
    c.post(f"/api/exam/sessions/{sid}/answers", headers=h, json={
        "position": 1, "selected": [0], "started_at": _now_iso(),   # wrong
    })
    c.post(f"/api/exam/sessions/{sid}/answers", headers=h, json={
        "position": 2, "answer_text": "exam essay", "started_at": _now_iso(),
    })

    r = c.post(f"/api/papers/sessions/{sid}/switch-mode",
               json={"mode": "practice"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    new_id = body["session_id"]
    assert body["kind"] == "practice"
    assert body["paper_id"] == str(paper.id)

    # old exam aborted, never finished
    old = db.get(ExamSession, uuid.UUID(sid))
    assert old.status.value == "aborted"

    ps = db.get(PracticeSession, uuid.UUID(new_id))
    assert ps.status.value == "in_progress"
    assert ps.config["paper_id"] == str(paper.id)
    # carried exam wall-clock elapsed seeds the practice clock
    assert ps.config.get("elapsed_seconds", 0) >= 0
    # answers copied + judged, essay pending self-assessment
    answers = {
        a.question_id: a for a in db.execute(
            select(PracticeAnswer).where(PracticeAnswer.session_id == ps.id)
        ).scalars().all()
    }
    assert answers[q1.id].is_correct is True
    assert answers[q2.id].is_correct is False
    assert answers[q2.id].user_answer == {"selected": [0]}
    assert answers[essay.id].is_correct is None
    assert answers[essay.id].user_answer == {"text": "exam essay"}
    assert ps.correct_count == 1

    # judged copies feed the wrong book exactly like a practice submit
    from app.models.practice import UserQuestionState
    st = db.execute(
        select(UserQuestionState).where(
            UserQuestionState.user_id == user.id,
            UserQuestionState.question_id == q2.id,
        )
    ).scalars().one()
    assert st.wrong_count == 1

    # delivery via the practice API works; essay text re-hydrates
    d = c.get(f"/api/practice/sessions/{new_id}/questions/2", headers=h)
    assert d.status_code == 200
    assert d.json()["previous_answer"]["text"] == "exam essay"


def test_switch_same_mode_is_noop(client):
    c, store, db = client
    h, user = _headers(db, store, email="sw-n@example.com")
    qs = [_seed_choice(db, user, stem=f"NO{i}") for i in range(2)]
    paper = _seed_paper(db, user, qs, name="NO paper")
    sid = _start_practice(client, h, paper).json()["id"]
    r = c.post(f"/api/papers/sessions/{sid}/switch-mode",
               json={"mode": "practice"}, headers=h)
    assert r.status_code == 200
    assert r.json()["session_id"] == sid
    assert r.json()["kind"] == "practice"
    # still in progress, no abandoned switcheroo
    assert db.get(PracticeSession, uuid.UUID(sid)).status.value == "in_progress"


def test_switch_error_paths(client):
    c, store, db = client
    h, user = _headers(db, store, email="sw-e@example.com")
    h2, user2 = _headers(db, store, email="sw-e2@example.com")
    _seed_blueprint(db)
    qs = [_seed_choice(db, user, stem=f"ER{i}") for i in range(2)]
    paper = _seed_paper(db, user, qs, name="ER paper")
    bank_qs = [_seed_choice(db, user, stem=f"EB{i}") for i in range(2)]
    _seed_dataset(db, user, "osg10", "CISSP OSG v10", bank_qs)

    # unknown session -> 404
    assert c.post("/api/papers/sessions/00000000-0000-0000-0000-000000000000/switch-mode",
                  json={"mode": "exam"}, headers=h).status_code == 404
    # someone else's session -> 404
    sid = _start_practice(client, h, paper).json()["id"]
    assert c.post(f"/api/papers/sessions/{sid}/switch-mode",
                  json={"mode": "exam"}, headers=h2).status_code == 404
    # finished session -> 409
    fin = _start_practice(client, h, paper).json()["id"]
    c.post(f"/api/practice/sessions/{fin}/finish", headers=h)
    assert c.post(f"/api/papers/sessions/{fin}/switch-mode",
                  json={"mode": "exam"}, headers=h).status_code == 409
    # non-paper (bank) session -> 422
    bs = c.post("/api/practice/sessions", headers=h, json={
        "dataset_slug": "osg10", "count": 10,
    }).json()["id"]
    assert c.post(f"/api/papers/sessions/{bs}/switch-mode",
                  json={"mode": "exam"}, headers=h).status_code == 422
