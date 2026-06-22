# Practice API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an authenticated learner start a scoped practice session, answer one question at a time with immediate judgment + explanation, mark questions, and get an end-of-session summary — with historical-integrity snapshots.

**Architecture:** New service module `app/services/practice.py` owns all logic/DB; new router `app/api/practice.py` delegates and commits after success. Candidate questions are chosen at session-creation time and stored positionally in `PracticeSession.config.question_ids`, making delivery stable across pause/resume. Answer judging reads correctness from the snapshot captured at answer time (NFR-DATA-01).

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Pydantic v2, PostgreSQL 16 (JSONB), Alembic. Tests use the real `cissp_test` DB with per-test SAVEPOINT rollback and `Base.metadata.create_all` (not migrations).

## Global Constraints

- Tests must NOT touch the dev `cissp` DB — use `cissp_test` (and `cissp_migtest` for migration drift).
- Soft-delete only via `not_deleted(Question)`; never break historical answer records (NFR-DATA-02).
- Tenant scoping: `PracticeSession` is `organization_id`-scoped NOT NULL; question candidate queries are org-scoped.
- ORM/parameterized queries only — no raw string SQL.
- Service-layer backend: routes delegate to service; caller commits the session after successful mutations; `log_audit` flushes but does NOT commit.
- Exam/practice answer rule: a submitted answer cannot be revised within the same session.
- Audit action for practice mutations: `AuditAction.edit`.
- Permission gating: all `/api/practice/*` routes require `practice:read`.
- Default branch is `master`; work on a feature branch; never implement on master.

---

## File Structure

- **Create:** `backend/app/schemas/practice.py` — Pydantic schemas (SessionCreateIn, SessionOut, QuestionDeliveryOut, AnswerIn, AnswerResultOut, SessionSummaryOut, QuestionStateIn).
- **Modify:** `backend/app/models/practice.py` — add `config JSONB` + `paused_at` columns to `PracticeSession`.
- **Create:** `backend/app/alembic/versions/<autogen>_practice_session_config.py` — migration adding the two columns.
- **Create:** `backend/app/services/practice.py` — service layer: exceptions, session creation (scope/subset/order), delivery, answer+judge, pause/resume, finish+summary, user-question-state.
- **Create:** `backend/app/api/practice.py` — HTTP router.
- **Modify:** `backend/app/main.py` — register the practice router.
- **Create:** `backend/tests/test_practice_service.py` — service-layer tests.
- **Create:** `backend/tests/test_practice_api.py` — HTTP tests.

All file paths below are relative to the repo root unless a `cd backend` is shown.

---

## Task 1: Schemas + model columns + migration

**Files:**
- Create: `backend/app/schemas/practice.py`
- Modify: `backend/app/models/practice.py:12-24`
- Create: `backend/app/alembic/versions/<autogen>_practice_session_config.py`
- Test: `backend/tests/test_practice_service.py`

**Interfaces:**
- Produces: `SessionCreateIn`, `SessionOut`, `QuestionDeliveryOut`, `AnswerIn`, `AnswerResultOut`, `SessionSummaryOut`, `QuestionStateIn` schema classes; `PracticeSession.config` (JSONB) + `PracticeSession.paused_at` (DateTime nullable).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_practice_service.py`:

```python
"""Service-layer tests for practice API (sub-project E)."""

import pytest

from app.models.auth import Organization, User
from app.models.enums import (
    OrgKind,
    QuestionStatus,
    QuestionType,
    TextFormat,
)
from app.models.question import Question, QuestionOption
from app.schemas.practice import (
    AnswerIn,
    SessionCreateIn,
    SessionSummaryOut,
)
from app.services import practice as svc


def _org(db_session, slug="t"):
    org = Organization(name="T", slug=slug, kind=OrgKind.personal)
    db_session.add(org)
    db_session.flush()
    return org


def _actor(db_session, org, email="learner@example.com"):
    user = User(
        email=email,
        password_hash="x",
        display_name="L",
        default_organization_id=org.id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _question(db_session, org, actor, *, stem="q", qtype=QuestionType.single_choice,
              difficulty=None, options=None):
    q = Question(
        organization_id=org.id,
        question_type=qtype,
        stem=stem,
        stem_format=TextFormat.markdown,
        status=QuestionStatus.published,
        difficulty=difficulty,
        created_by_id=actor.id,
    )
    db_session.add(q)
    db_session.flush()
    opts = options if options is not None else [
        (0, "A", True),
        (1, "B", False),
    ]
    for order_index, content, is_correct in opts:
        db_session.add(QuestionOption(
            question_id=q.id, order_index=order_index, content=content,
            content_format=TextFormat.markdown, is_correct=is_correct,
        ))
    db_session.flush()
    return q


def test_session_has_config_and_paused_at_columns(db_session):
    """PracticeSession must expose config (JSONB) and paused_at columns."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    session = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=1),
    )
    assert session.config is not None
    assert "question_ids" in session.config
    assert session.paused_at is None
    assert session.status.value == "in_progress"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source venv/bin/activate && pytest tests/test_practice_service.py::test_session_has_config_and_paused_at_columns -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.schemas.practice'` (and `app.services.practice`).

- [ ] **Step 3: Create the schemas file**

Create `backend/app/schemas/practice.py`:

```python
"""Pydantic schemas for the practice API."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Subset = Literal["all", "unpracticed", "wrong", "bookmarked", "needs_review"]
OrderMode = Literal["random", "sequential", "easy_to_hard"]


class SessionCreateIn(BaseModel):
    count: int = Field(ge=1, le=200)
    subset: Subset = "all"
    order_mode: OrderMode = "random"
    domain_id: uuid.UUID | None = None
    book_id: uuid.UUID | None = None
    chapter_ids: list[uuid.UUID] = Field(default_factory=list)
    question_type: str | None = None
    difficulty: int | None = None
    tag_id: uuid.UUID | None = None


class SessionOut(BaseModel):
    id: uuid.UUID
    status: str
    total_questions: int
    correct_count: int
    started_at: datetime
    ended_at: datetime | None = None
    paused_at: datetime | None = None
    config: dict


class OptionDelivery(BaseModel):
    id: uuid.UUID
    order_index: int
    content: str
    content_format: str


class QuestionDeliveryOut(BaseModel):
    session_id: uuid.UUID
    position: int
    total: int
    question_id: uuid.UUID
    stem: str
    question_type: str
    options: list[OptionDelivery]
    elapsed_ms: int
    previous_answer: dict | None = None


class AnswerIn(BaseModel):
    position: int = Field(ge=0)
    selected: list[int]
    started_at: datetime


class PerOptionExplanation(BaseModel):
    order_index: int
    is_correct: bool
    explanation: str | None = None


class AnswerResultOut(BaseModel):
    is_correct: bool
    correct_indexes: list[int]
    selected_indexes: list[int]
    correct_rationale: str | None = None
    key_point_summary: str | None = None
    per_option: list[PerOptionExplanation]
    mapping: dict
    history: list[dict]


class DomainBreakdown(BaseModel):
    domain_id: uuid.UUID | None
    domain_name: str | None
    answered: int
    correct: int


class WrongQuestion(BaseModel):
    question_id: uuid.UUID
    stem: str
    selected_indexes: list[int]
    correct_indexes: list[int]


class SessionSummaryOut(BaseModel):
    session_id: uuid.UUID
    total_questions: int
    answered_count: int
    correct_count: int
    accuracy: float
    total_time_spent_ms: int
    domains: list[DomainBreakdown]
    wrong_questions: list[WrongQuestion]


class QuestionStateIn(BaseModel):
    is_bookmarked: bool | None = None
    is_flagged_review: bool | None = None
    is_mastered: bool | None = None
    is_questioned: bool | None = None
    note: str | None = None
```

- [ ] **Step 4: Add the two columns to PracticeSession**

In `backend/app/models/practice.py`, add imports `JSONB` to the sqlalchemy.dialects.postgresql import line (it already imports from that module) and add two columns to the `PracticeSession` class. Replace the existing import line and class body:

```python
from sqlalchemy.dialects.postgresql import JSONB
```

Add inside `PracticeSession`, after `ended_at`:

```python
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

(The `DateTime` and `text` names are already imported at the top of the file.)

- [ ] **Step 5: Create the migration**

Run: `cd backend && source venv/bin/activate && alembic revision --autogenerate -m "practice session config + paused_at"`

Open the generated file. It should contain `op.add_column('practice_sessions', ...)` for both columns and a `server_default`. Edit the `config` add_column to use `server_default=sa.text("'{}'"))` so existing rows get an empty object. Verify the `downgrade()` drops both columns.

- [ ] **Step 6: Create a minimal service stub so the test can import it**

Create `backend/app/services/practice.py`:

```python
"""Practice session service (sub-project E).

Owns session creation, question delivery, answer judging (from snapshot),
pause/resume, finish/summary, and per-user question state.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.queries import not_deleted
from app.models.admin import AuditLog
from app.models.enums import AuditAction, MasteryLevel, PracticeSessionStatus, QuestionStatus
from app.models.practice import PracticeAnswer, PracticeSession, UserQuestionState
from app.models.question import Explanation, Question, QuestionMapping, QuestionOption
from app.schemas.practice import (
    AnswerIn,
    AnswerResultOut,
    QuestionStateIn,
    SessionCreateIn,
    SessionSummaryOut,
)
from app.services.audit import log_audit
from app.services.snapshot import snapshot_question


class ValidationError(ValueError):
    pass


class NotFound(LookupError):
    pass


class ConflictError(ValueError):
    pass


def create_session(session: Session, *, org_id, actor_id, payload: SessionCreateIn) -> PracticeSession:
    raise NotImplementedError
```

- [ ] **Step 7: Run test to verify it fails at the right place**

Run: `cd backend && source venv/bin/activate && pytest tests/test_practice_service.py::test_session_has_config_and_paused_at_columns -v`
Expected: FAIL with `NotImplementedError` (imports + columns now exist; logic not yet implemented).

- [ ] **Step 8: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/schemas/practice.py backend/app/models/practice.py backend/app/alembic/versions backend/tests/test_practice_service.py backend/app/services/practice.py
git commit -m "feat(practice): schemas + PracticeSession config/paused_at columns + migration"
```

---

## Task 2: Session creation — scope, subset, ordering

**Files:**
- Modify: `backend/app/services/practice.py` (implement `create_session`)
- Test: `backend/tests/test_practice_service.py`

**Interfaces:**
- Consumes: `SessionCreateIn` (Task 1), `Question`/`QuestionMapping`/`PracticeAnswer`/`UserQuestionState` models.
- Produces: `create_session(session, *, org_id, actor_id, payload: SessionCreateIn) -> PracticeSession` whose `.config == {"subset", "order_mode", "count", "question_ids": [...]}`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_practice_service.py`:

```python
def test_create_session_random_pick(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    for i in range(5):
        _question(db_session, org, actor, stem=f"q{i}")
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=3),
    )
    assert s.total_questions == 3
    assert len(s.config["question_ids"]) == 3
    assert s.config["subset"] == "all"
    assert s.config["order_mode"] == "random"


def test_create_session_scope_by_domain(db_session):
    from app.models.taxonomy import ExamBlueprint, ExamDomain

    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = ExamBlueprint(version_label="v1", effective_date="2026-04-15",
                       min_items=100, max_items=150, duration_minutes=180,
                       passing_score=700, max_score=1000, is_current=False)
    db_session.add(bp)
    db_session.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=10)
    db_session.add(dom)
    db_session.flush()
    in_q = _question(db_session, org, actor, stem="in")
    out_q = _question(db_session, org, actor, stem="out")
    db_session.add(QuestionMapping(question_id=in_q.id, domain_id=dom.id))
    db_session.flush()
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=10, domain_id=dom.id),
    )
    assert s.total_questions == 1
    assert s.config["question_ids"] == [str(in_q.id)]


def test_create_session_empty_scope_rejected(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    with pytest.raises(svc.ValidationError):
        svc.create_session(
            db_session, org_id=org.id, actor_id=actor.id,
            payload=SessionCreateIn(count=10),
        )


def test_create_session_subset_unpracticed(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    q1 = _question(db_session, org, actor, stem="done")
    q2 = _question(db_session, org, actor, stem="new")
    # simulate a prior answer on q1 in another session
    other = PracticeSession(
        user_id=actor.id, organization_id=org.id,
        status=PracticeSessionStatus.completed, total_questions=1,
    )
    db_session.add(other)
    db_session.flush()
    db_session.add(PracticeAnswer(
        session_id=other.id, user_id=actor.id, question_id=q1.id,
        question_snapshot={}, options_snapshot=[], user_answer={"selected": [0]},
        is_correct=True,
    ))
    db_session.flush()
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=10, subset="unpracticed"),
    )
    assert s.config["question_ids"] == [str(q2.id)]


def test_create_session_scope_by_chapter(db_session):
    from app.models.question import Book, Chapter

    org = _org(db_session)
    actor = _actor(db_session, org)
    book = Book(organization_id=org.id, title="B")
    db_session.add(book)
    db_session.flush()
    ch = Chapter(organization_id=org.id, book_id=book.id, order_index=0, title="C1")
    db_session.add(ch)
    db_session.flush()
    in_q = _question(db_session, org, actor, stem="in")
    _question(db_session, org, actor, stem="out")
    db_session.add(QuestionMapping(question_id=in_q.id, chapter_id=ch.id))
    db_session.flush()
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=10, chapter_ids=[ch.id]),
    )
    assert s.config["question_ids"] == [str(in_q.id)]
```

(Add `PracticeSession`, `PracticeAnswer`, `QuestionMapping` to the imports at the top of the test file's inline `from app.models...` blocks as needed — `QuestionMapping` is imported inside the test functions above, which is fine.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_practice_service.py -v -k create_session`
Expected: FAIL — `NotImplementedError`.

- [ ] **Step 3: Implement create_session**

Replace the `create_session` stub in `backend/app/services/practice.py` with:

```python
def _candidate_question_ids(
    session: Session, *, org_id, payload: SessionCreateIn
) -> list[uuid.UUID]:
    stmt = select(Question.id).where(
        Question.organization_id == org_id,
        Question.status == QuestionStatus.published,
        not_deleted(Question),
    )
    if payload.domain_id is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(
                QuestionMapping.domain_id == payload.domain_id
            )
        ))
    if payload.book_id is not None:
        from app.models.question import Chapter

        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(
                QuestionMapping.chapter_id.in_(
                    select(Chapter.id).where(Chapter.book_id == payload.book_id)
                )
            )
        ))
    if payload.chapter_ids:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(
                QuestionMapping.chapter_id.in_(payload.chapter_ids)
            )
        ))
    if payload.tag_id is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(QuestionMapping.tag_id == payload.tag_id)
        ))
    if payload.question_type is not None:
        stmt = stmt.where(Question.question_type == payload.question_type)
    if payload.difficulty is not None:
        stmt = stmt.where(Question.difficulty == payload.difficulty)
    return [row[0] for row in session.execute(stmt).all()]


def _apply_subset(
    session: Session, *, user_id, candidate_ids: list[uuid.UUID], subset: str
) -> list[uuid.UUID]:
    if subset == "all" or not candidate_ids:
        return candidate_ids
    if subset == "unpracticed":
        answered = set(
            session.execute(
                select(PracticeAnswer.question_id).where(
                    PracticeAnswer.user_id == user_id,
                    PracticeAnswer.question_id.in_(candidate_ids),
                )
            ).scalars().all()
        )
        return [q for q in candidate_ids if q not in answered]
    if subset == "wrong":
        rows = session.execute(
            select(PracticeAnswer.question_id).where(
                PracticeAnswer.user_id == user_id,
                PracticeAnswer.question_id.in_(candidate_ids),
                PracticeAnswer.is_correct.is_(False),
            )
        ).scalars().all()
        seen = set(rows)
        return [q for q in candidate_ids if q in seen]
    if subset == "bookmarked":
        rows = session.execute(
            select(UserQuestionState.question_id).where(
                UserQuestionState.user_id == user_id,
                UserQuestionState.is_bookmarked.is_(True),
                UserQuestionState.question_id.in_(candidate_ids),
            )
        ).scalars().all()
        seen = set(rows)
        return [q for q in candidate_ids if q in seen]
    if subset == "needs_review":
        rows = session.execute(
            select(UserQuestionState.question_id).where(
                UserQuestionState.user_id == user_id,
                UserQuestionState.is_flagged_review.is_(True),
                UserQuestionState.question_id.in_(candidate_ids),
            )
        ).scalars().all()
        seen = set(rows)
        return [q for q in candidate_ids if q in seen]
    return candidate_ids


def _order_questions(
    session: Session, *, ids: list[uuid.UUID], order_mode: str
) -> list[uuid.UUID]:
    if not ids:
        return []
    if order_mode == "random":
        return list(session.execute(
            select(Question.id)
            .where(Question.id.in_(ids))
            .order_by(func.random())
        ).scalars().all())
    if order_mode == "easy_to_hard":
        return list(session.execute(
            select(Question.id)
            .where(Question.id.in_(ids))
            .order_by(Question.difficulty.asc().nulls_last(), Question.created_at.asc())
        ).scalars().all())
    # sequential
    return list(session.execute(
        select(Question.id)
        .where(Question.id.in_(ids))
        .order_by(Question.created_at.asc())
    ).scalars().all())


def create_session(
    session: Session, *, org_id, actor_id, payload: SessionCreateIn
) -> PracticeSession:
    candidate_ids = _candidate_question_ids(session, org_id=org_id, payload=payload)
    candidate_ids = _apply_subset(
        session, user_id=actor_id, candidate_ids=candidate_ids, subset=payload.subset
    )
    ordered = _order_questions(session, ids=candidate_ids, order_mode=payload.order_mode)
    ordered = ordered[: payload.count]
    if not ordered:
        raise ValidationError("no questions match the selected scope")
    ps = PracticeSession(
        user_id=actor_id,
        organization_id=org_id,
        status=PracticeSessionStatus.in_progress,
        total_questions=len(ordered),
        config={
            "subset": payload.subset,
            "order_mode": payload.order_mode,
            "count": payload.count,
            "question_ids": [str(qid) for qid in ordered],
        },
    )
    session.add(ps)
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=actor_id, organization_id=org_id,
        entity_type="practice_session", entity_id=str(ps.id),
        details={"total_questions": len(ordered)},
    )
    return ps
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_practice_service.py -v -k create_session`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/services/practice.py backend/tests/test_practice_service.py
git commit -m "feat(practice): session creation with scope/subset/ordering"
```

---

## Task 3: Question delivery + answer judging

**Files:**
- Modify: `backend/app/services/practice.py` (add `get_question_at`, `submit_answer`)
- Test: `backend/tests/test_practice_service.py`

**Interfaces:**
- Consumes: `create_session` (Task 2), `snapshot_question` (existing).
- Produces: `get_question_at(session, *, session_id, position, user_id) -> dict`, `submit_answer(session, *, session_id, user_id, payload: AnswerIn) -> AnswerResultOut`. Answer judging reads correctness from the snapshot.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_practice_service.py`:

```python
def _start(db_session, org, actor, count=1):
    return svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=count, order_mode="sequential"),
    )


def test_get_question_strips_correctness(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor, stem="q1")
    s = _start(db_session, org, actor)
    out = svc.get_question_at(
        db_session, session_id=s.id, position=0, user_id=actor.id
    )
    assert out["position"] == 0
    assert out["total"] == 1
    assert out["stem"] == "q1"
    # correctness must NOT be leaked before answering
    for opt in out["options"]:
        assert "is_correct" not in opt


def test_submit_answer_judges_from_snapshot(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor, stem="q1")  # option 0 correct
    s = _start(db_session, org, actor)
    started = datetime.now(timezone.utc)
    result = svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=started),
    )
    assert result.is_correct is True
    assert result.correct_indexes == [0]
    assert result.selected_indexes == [0]


def test_submit_answer_incorrect(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor, stem="q1")  # 0 correct
    s = _start(db_session, org, actor)
    result = svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[1], started_at=datetime.now(timezone.utc)),
    )
    assert result.is_correct is False
    assert s.correct_count == 0


def test_submit_answer_multiple_choice(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(
        db_session, org, actor, stem="multi", qtype=QuestionType.multiple_choice,
        options=[(0, "A", True), (1, "B", True), (2, "C", False)],
    )
    s = _start(db_session, org, actor)
    # select only A -> not fully correct
    r1 = svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    assert r1.is_correct is False


def test_submit_answer_persists_snapshot(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    q = _question(db_session, org, actor, stem="q1")
    s = _start(db_session, org, actor)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    ans = db_session.query(PracticeAnswer).filter_by(session_id=s.id).one()
    assert ans.question_snapshot["question_id"] == str(q.id)
    assert ans.is_correct is True
    assert ans.user_answer == {"selected": [0]}


def test_re_answer_refused(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor)
    s = _start(db_session, org, actor)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    with pytest.raises(svc.ConflictError):
        svc.submit_answer(
            db_session, session_id=s.id, user_id=actor.id,
            payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
        )
```

Add `from datetime import datetime, timezone` to the test file imports.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_practice_service.py -v -k "get_question or submit_answer or re_answer"`
Expected: FAIL — `AttributeError`/`NotImplemented` for missing functions.

- [ ] **Step 3: Implement get_question_at and submit_answer**

Add to `backend/app/services/practice.py`:

```python
def _load_session(session: Session, session_id, user_id) -> PracticeSession:
    ps = session.get(PracticeSession, session_id)
    if ps is None or ps.user_id != user_id:
        raise NotFound(f"practice session {session_id} not found")
    return ps


def _options_for(session: Session, question_id) -> list[QuestionOption]:
    return list(
        session.execute(
            select(QuestionOption)
            .where(QuestionOption.question_id == question_id)
            .order_by(QuestionOption.order_index)
        ).scalars().all()
    )


def get_question_at(
    session: Session, *, session_id, position: int, user_id
) -> dict:
    ps = _load_session(session, session_id, user_id)
    qids = ps.config.get("question_ids", [])
    if position < 0 or position >= len(qids):
        raise ValidationError("position out of range")
    question = session.get(Question, uuid.UUID(qids[position]))
    if question is None or question.deleted_at is not None:
        raise NotFound("question no longer available")
    options = _options_for(session, question.id)
    now = datetime.now(timezone.utc)
    elapsed_ms = int((now - ps.started_at.replace(tzinfo=timezone.utc)).total_seconds() * 1000)
    prev = session.execute(
        select(PracticeAnswer).where(
            PracticeAnswer.session_id == ps.id, PracticeAnswer.question_id == question.id
        )
    ).scalars().first()
    return {
        "session_id": str(ps.id),
        "position": position,
        "total": len(qids),
        "question_id": str(question.id),
        "stem": question.stem,
        "question_type": question.question_type.value,
        "options": [
            {
                "id": str(o.id),
                "order_index": o.order_index,
                "content": o.content,
                "content_format": o.content_format.value,
            }
            for o in options
        ],
        "elapsed_ms": elapsed_ms,
        "previous_answer": (
            {"selected": prev.user_answer.get("selected"), "is_correct": prev.is_correct}
            if prev else None
        ),
    }


def _judge(snapshot: dict, selected: list[int]) -> tuple[bool, list[int]]:
    correct_indexes = [
        o["order_index"] for o in snapshot["options"] if o["is_correct"]
    ]
    return (set(selected) == set(correct_indexes)), correct_indexes


def _mapping_out(session: Session, question_id) -> dict:
    m = session.execute(
        select(QuestionMapping).where(QuestionMapping.question_id == question_id)
    ).scalars().first()
    out: dict = {}
    if m is not None:
        out["domain_id"] = str(m.domain_id) if m.domain_id else None
        out["chapter_id"] = str(m.chapter_id) if m.chapter_id else None
        out["knowledge_point_id"] = str(m.knowledge_point_id) if m.knowledge_point_id else None
    return out


def _history_out(session: Session, *, user_id, question_id, exclude_session_id) -> list[dict]:
    rows = session.execute(
        select(PracticeAnswer).where(
            PracticeAnswer.user_id == user_id,
            PracticeAnswer.question_id == question_id,
            PracticeAnswer.session_id != exclude_session_id,
        ).order_by(PracticeAnswer.answered_at.desc())
    ).scalars().all()
    return [
        {
            "session_id": str(r.session_id),
            "is_correct": r.is_correct,
            "answered_at": r.answered_at.isoformat() if r.answered_at else None,
        }
        for r in rows
    ]


def submit_answer(
    session: Session, *, session_id, user_id, payload: AnswerIn
) -> AnswerResultOut:
    ps = _load_session(session, session_id, user_id)
    if ps.status != PracticeSessionStatus.in_progress:
        raise ConflictError("session is not in progress")
    if ps.paused_at is not None:
        raise ConflictError("session is paused")
    qids = ps.config.get("question_ids", [])
    if payload.position < 0 or payload.position >= len(qids):
        raise ValidationError("position out of range")
    question_id = uuid.UUID(qids[payload.position])
    existing = session.execute(
        select(PracticeAnswer).where(
            PracticeAnswer.session_id == ps.id, PracticeAnswer.question_id == question_id
        )
    ).scalars().first()
    if existing is not None:
        raise ConflictError("this question has already been answered in this session")
    question = session.get(Question, question_id)
    if question is None or question.deleted_at is not None:
        raise NotFound("question no longer available")
    options = _options_for(session, question_id)
    snap = snapshot_question(question, options)
    is_correct, correct_indexes = _judge(snap, payload.selected)
    now = datetime.now(timezone.utc)
    started = payload.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    time_spent_ms = max(0, int((now - started).total_seconds() * 1000))
    ans = PracticeAnswer(
        session_id=ps.id,
        user_id=user_id,
        question_id=question_id,
        question_snapshot=snap,
        options_snapshot=snap["options"],
        user_answer={"selected": payload.selected},
        is_correct=is_correct,
        time_spent_ms=time_spent_ms,
    )
    session.add(ans)
    if is_correct:
        ps.correct_count = (ps.correct_count or 0) + 1
    # upsert user question state mastery
    state = session.execute(
        select(UserQuestionState).where(
            UserQuestionState.user_id == user_id,
            UserQuestionState.question_id == question_id,
        )
    ).scalars().first()
    new_level = MasteryLevel.mastered if is_correct else MasteryLevel.learning
    if state is None:
        state = UserQuestionState(
            user_id=user_id, question_id=question_id, mastery_level=new_level
        )
        session.add(state)
    else:
        state.mastery_level = new_level
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=user_id,
        organization_id=ps.organization_id, entity_type="practice_answer",
        entity_id=str(ans.id), details={"is_correct": is_correct},
    )
    explanation = session.execute(
        select(Explanation).where(Explanation.question_id == question_id)
    ).scalars().first()
    return AnswerResultOut(
        is_correct=is_correct,
        correct_indexes=correct_indexes,
        selected_indexes=list(payload.selected),
        correct_rationale=explanation.correct_answer_rationale if explanation else None,
        key_point_summary=explanation.key_point_summary if explanation else None,
        per_option=[
            {
                "order_index": o["order_index"],
                "is_correct": o["is_correct"],
                "explanation": next(
                    (opt.explanation for opt in options if opt.order_index == o["order_index"]),
                    None,
                ),
            }
            for o in snap["options"]
        ],
        mapping=_mapping_out(session, question_id),
        history=_history_out(session, user_id=user_id, question_id=question_id,
                             exclude_session_id=ps.id),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_practice_service.py -v -k "get_question or submit_answer or re_answer"`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/services/practice.py backend/tests/test_practice_service.py
git commit -m "feat(practice): question delivery + answer judging from snapshot"
```

---

## Task 4: Pause / resume / finish + summary

**Files:**
- Modify: `backend/app/services/practice.py` (add `pause_session`, `resume_session`, `finish_session`, `get_summary`)
- Test: `backend/tests/test_practice_service.py`

**Interfaces:**
- Consumes: `submit_answer` (Task 3).
- Produces: `pause_session`, `resume_session`, `finish_session(...) -> SessionSummaryOut`, `get_summary(...) -> SessionSummaryOut`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_practice_service.py`:

```python
def test_pause_resume(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor)
    s = _start(db_session, org, actor)
    svc.pause_session(db_session, session_id=s.id, user_id=actor.id)
    assert db_session.get(PracticeSession, s.id).paused_at is not None
    with pytest.raises(svc.ConflictError):
        svc.submit_answer(
            db_session, session_id=s.id, user_id=actor.id,
            payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
        )
    svc.resume_session(db_session, session_id=s.id, user_id=actor.id)
    assert db_session.get(PracticeSession, s.id).paused_at is None
    r = svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    assert r.is_correct is True


def test_finish_summary(db_session):
    from app.models.taxonomy import ExamBlueprint, ExamDomain

    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = ExamBlueprint(version_label="v1", effective_date="2026-04-15",
                       min_items=100, max_items=150, duration_minutes=180,
                       passing_score=700, max_score=1000, is_current=False)
    db_session.add(bp)
    db_session.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=10)
    db_session.add(dom)
    db_session.flush()
    q1 = _question(db_session, org, actor, stem="right")  # 0 correct
    q2 = _question(db_session, org, actor, stem="wrong")  # 0 correct
    db_session.add(QuestionMapping(question_id=q1.id, domain_id=dom.id))
    db_session.add(QuestionMapping(question_id=q2.id, domain_id=dom.id))
    db_session.flush()
    s = _start(db_session, org, actor, count=2)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=1, selected=[1], started_at=datetime.now(timezone.utc)),
    )
    summary = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert summary.total_questions == 2
    assert summary.answered_count == 2
    assert summary.correct_count == 1
    assert summary.accuracy == 0.5
    assert len(summary.domains) == 1
    assert summary.domains[0].answered == 2
    assert summary.domains[0].correct == 1
    assert len(summary.wrong_questions) == 1
    assert summary.wrong_questions[0].question_id == q2.id
    assert db_session.get(PracticeSession, s.id).status == PracticeSessionStatus.completed


def test_finish_idempotent(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor)
    s = _start(db_session, org, actor)
    a = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    b = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert a.correct_count == b.correct_count


def test_other_user_session_not_found(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    intruder = _actor(db_session, org, email="other@example.com")
    _question(db_session, org, actor)
    s = _start(db_session, org, actor)
    with pytest.raises(svc.NotFound):
        svc.finish_session(db_session, session_id=s.id, user_id=intruder.id)
```

Add `PracticeSessionStatus` to the test file imports from `app.models.enums`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_practice_service.py -v -k "pause_resume or finish or other_user"`
Expected: FAIL — missing functions.

- [ ] **Step 3: Implement pause/resume/finish**

Add to `backend/app/services/practice.py`:

```python
def pause_session(session: Session, *, session_id, user_id) -> PracticeSession:
    ps = _load_session(session, session_id, user_id)
    if ps.status != PracticeSessionStatus.in_progress:
        raise ConflictError("session is not in progress")
    ps.paused_at = datetime.now(timezone.utc)
    session.flush()
    return ps


def resume_session(session: Session, *, session_id, user_id) -> PracticeSession:
    ps = _load_session(session, session_id, user_id)
    if ps.status != PracticeSessionStatus.in_progress:
        raise ConflictError("session is not in progress")
    ps.paused_at = None
    session.flush()
    return ps


def _build_summary(session: Session, ps: PracticeSession) -> SessionSummaryOut:
    answers = list(
        session.execute(
            select(PracticeAnswer).where(PracticeAnswer.session_id == ps.id)
        ).scalars().all()
    )
    correct = sum(1 for a in answers if a.is_correct)
    total_time = sum((a.time_spent_ms or 0) for a in answers)

    # domain breakdown via mappings
    domain_ids: dict = {}
    for a in answers:
        m = session.execute(
            select(QuestionMapping).where(QuestionMapping.question_id == a.question_id)
        ).scalars().first()
        did = str(m.domain_id) if (m and m.domain_id) else None
        entry = domain_ids.setdefault(did, {"answered": 0, "correct": 0, "name": None})
        entry["answered"] += 1
        if a.is_correct:
            entry["correct"] += 1
    # resolve domain names
    from app.models.taxonomy import ExamDomain

    for did, entry in domain_ids.items():
        if did is not None:
            d = session.get(ExamDomain, uuid.UUID(did))
            entry["name"] = d.name if d else None

    wrong = [
        {
            "question_id": str(a.question_id),
            "stem": a.question_snapshot.get("stem", ""),
            "selected_indexes": (a.user_answer or {}).get("selected", []),
            "correct_indexes": [
                o["order_index"] for o in a.options_snapshot if o["is_correct"]
            ],
        }
        for a in answers if not a.is_correct
    ]
    from app.schemas.practice import DomainBreakdown, WrongQuestion

    return SessionSummaryOut(
        session_id=ps.id,
        total_questions=ps.total_questions,
        answered_count=len(answers),
        correct_count=correct,
        accuracy=(correct / len(answers)) if answers else 0.0,
        total_time_spent_ms=total_time,
        domains=[
            DomainBreakdown(
                domain_id=uuid.UUID(did) if did else None,
                domain_name=entry["name"],
                answered=entry["answered"],
                correct=entry["correct"],
            )
            for did, entry in domain_ids.items()
        ],
        wrong_questions=[WrongQuestion(**w) for w in wrong],
    )


def finish_session(session: Session, *, session_id, user_id) -> SessionSummaryOut:
    ps = _load_session(session, session_id, user_id)
    if ps.status != PracticeSessionStatus.completed:
        ps.status = PracticeSessionStatus.completed
        ps.ended_at = datetime.now(timezone.utc)
        session.flush()
        log_audit(
            session, action=AuditAction.edit, actor_id=user_id,
            organization_id=ps.organization_id, entity_type="practice_session",
            entity_id=str(ps.id), details={"finished": True},
        )
    return _build_summary(session, ps)


def get_summary(session: Session, *, session_id, user_id) -> SessionSummaryOut:
    ps = _load_session(session, session_id, user_id)
    return _build_summary(session, ps)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_practice_service.py -v -k "pause_resume or finish or other_user"`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/services/practice.py backend/tests/test_practice_service.py
git commit -m "feat(practice): pause/resume + finish summary with domain breakdown"
```

---

## Task 5: User-question state (marks + notes)

**Files:**
- Modify: `backend/app/services/practice.py` (add `set_question_state`)
- Test: `backend/tests/test_practice_service.py`

**Interfaces:**
- Consumes: `Question` (tenant check).
- Produces: `set_question_state(session, *, user_id, org_id, question_id, payload: QuestionStateIn) -> UserQuestionState`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_practice_service.py`:

```python
def test_set_question_state_upsert(db_session):
    from app.schemas.practice import QuestionStateIn

    org = _org(db_session)
    actor = _actor(db_session, org)
    q = _question(db_session, org, actor)
    svc.set_question_state(
        db_session, user_id=actor.id, org_id=org.id, question_id=q.id,
        payload=QuestionStateIn(is_bookmarked=True, note="hard"),
    )
    svc.set_question_state(
        db_session, user_id=actor.id, org_id=org.id, question_id=q.id,
        payload=QuestionStateIn(is_flagged_review=True),
    )
    state = db_session.query(UserQuestionState).filter_by(
        user_id=actor.id, question_id=q.id
    ).one()
    assert state.is_bookmarked is True
    assert state.is_flagged_review is True
    assert state.note == "hard"


def test_set_question_state_wrong_tenant_not_found(db_session):
    from app.schemas.practice import QuestionStateIn

    org = _org(db_session)
    other_org = _org(db_session, slug="o2")
    actor = _actor(db_session, org)
    q = _question(db_session, org, actor)
    with pytest.raises(svc.NotFound):
        svc.set_question_state(
            db_session, user_id=actor.id, org_id=other_org.id, question_id=q.id,
            payload=QuestionStateIn(is_bookmarked=True),
        )
```

Add `UserQuestionState` to the test file imports from `app.models.practice`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_practice_service.py -v -k set_question_state`
Expected: FAIL — missing function.

- [ ] **Step 3: Implement set_question_state**

Add to `backend/app/services/practice.py`:

```python
def set_question_state(
    session: Session, *, user_id, org_id, question_id, payload: QuestionStateIn
) -> UserQuestionState:
    q = session.get(Question, question_id)
    if q is None or q.deleted_at is not None or q.organization_id != org_id:
        raise NotFound(f"question {question_id} not found")
    state = session.execute(
        select(UserQuestionState).where(
            UserQuestionState.user_id == user_id,
            UserQuestionState.question_id == question_id,
        )
    ).scalars().first()
    if state is None:
        state = UserQuestionState(user_id=user_id, question_id=question_id)
        session.add(state)
    if payload.is_bookmarked is not None:
        state.is_bookmarked = payload.is_bookmarked
    if payload.is_flagged_review is not None:
        state.is_flagged_review = payload.is_flagged_review
    if payload.is_mastered is not None:
        state.is_mastered = payload.is_mastered
        if payload.is_mastered:
            state.mastery_level = MasteryLevel.mastered
    if payload.is_questioned is not None:
        state.is_questioned = payload.is_questioned
    if payload.note is not None:
        state.note = payload.note
    session.flush()
    return state
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_practice_service.py -v -k set_question_state`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/services/practice.py backend/tests/test_practice_service.py
git commit -m "feat(practice): user-question state upsert (marks + notes)"
```

---

## Task 6: HTTP router + registration

**Files:**
- Create: `backend/app/api/practice.py`
- Modify: `backend/app/main.py:7-47` (import + include_router)

**Interfaces:**
- Consumes: all service functions (Tasks 2–5), schemas (Task 1).
- Produces: `/api/practice/*` routes, all gated by `require_permission("practice:read")`, error mapping NotFound→404, ValidationError→422, ConflictError→409, caller commits after success.

- [ ] **Step 1: Write the failing HTTP tests**

Create `backend/tests/test_practice_api.py`:

```python
"""HTTP tests for practice API (sub-project E)."""

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
```

Then add helper to seed a published question via the questions API and the happy-path tests. Append:

```python
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
    return r.json()["id"]


def test_happy_path(capsys, client):
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
    import datetime as dt
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
    import datetime as dt
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_practice_api.py -v`
Expected: FAIL — routes do not exist (404 from FastAPI, or 422/KeyError on JSON access).

- [ ] **Step 3: Create the router**

Create `backend/app/api/practice.py`:

```python
"""Practice HTTP API."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dependencies import CurrentUser, require_permission
from app.schemas.practice import (
    AnswerIn,
    AnswerResultOut,
    QuestionDeliveryOut,
    QuestionStateIn,
    SessionCreateIn,
    SessionOut,
    SessionSummaryOut,
)
from app.services import practice as svc

router = APIRouter(prefix="/api/practice", tags=["practice"])


def _session_out(ps) -> SessionOut:
    return SessionOut(
        id=ps.id, status=ps.status.value, total_questions=ps.total_questions,
        correct_count=ps.correct_count, started_at=ps.started_at,
        ended_at=ps.ended_at, paused_at=ps.paused_at, config=ps.config or {},
    )


@router.post("/sessions", response_model=SessionOut)
def create_session(
    body: SessionCreateIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        ps = svc.create_session(
            session, org_id=current.org_id, actor_id=current.user.id, payload=body
        )
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(ps)
    return _session_out(ps)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        ps = svc._load_session(session, session_id, current.user.id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session not found")
    return _session_out(ps)


@router.get("/sessions/{session_id}/questions/{position}", response_model=QuestionDeliveryOut)
def get_question(
    session_id: uuid.UUID,
    position: int,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        return svc.get_question_at(
            session, session_id=session_id, position=position, user_id=current.user.id
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session not found")
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/sessions/{session_id}/answers", response_model=AnswerResultOut)
def submit_answer(
    session_id: uuid.UUID,
    body: AnswerIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        result = svc.submit_answer(
            session, session_id=session_id, user_id=current.user.id, payload=body
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session or question not found")
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return result


@router.post("/sessions/{session_id}/pause", response_model=SessionOut)
def pause_session(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        ps = svc.pause_session(session, session_id=session_id, user_id=current.user.id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session not found")
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    session.refresh(ps)
    return _session_out(ps)


@router.post("/sessions/{session_id}/resume", response_model=SessionOut)
def resume_session(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        ps = svc.resume_session(session, session_id=session_id, user_id=current.user.id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session not found")
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    session.refresh(ps)
    return _session_out(ps)


@router.post("/sessions/{session_id}/finish", response_model=SessionSummaryOut)
def finish_session(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        summary = svc.finish_session(
            session, session_id=session_id, user_id=current.user.id
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session not found")
    session.commit()
    return summary


@router.get("/sessions/{session_id}/summary", response_model=SessionSummaryOut)
def get_summary(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        return svc.get_summary(session, session_id=session_id, user_id=current.user.id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session not found")


@router.put("/questions/{question_id}/state")
def set_question_state(
    question_id: uuid.UUID,
    body: QuestionStateIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        state = svc.set_question_state(
            session, user_id=current.user.id, org_id=current.org_id,
            question_id=question_id, payload=body,
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="question not found")
    session.commit()
    return {
        "is_bookmarked": state.is_bookmarked,
        "is_flagged_review": state.is_flagged_review,
        "is_mastered": state.is_mastered,
        "is_questioned": state.is_questioned,
        "note": state.note,
    }
```

- [ ] **Step 4: Register the router**

In `backend/app/main.py`, add the import near the other router imports:

```python
from app.api.practice import router as practice_router
```

And after `app.include_router(questions_router)` add:

```python
    app.include_router(practice_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_practice_api.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/api/practice.py backend/app/main.py backend/tests/test_practice_api.py
git commit -m "feat(practice): HTTP router (/api/practice) + registration"
```

---

## Task 7: Full suite + migration drift + docs + finish branch

**Files:**
- Modify: `CLAUDE.md` (Current State paragraph)

- [ ] **Step 1: Run the full backend suite**

Run: `cd backend && source venv/bin/activate && pytest -q`
Expected: all pass (168 prior + new practice tests).

- [ ] **Step 2: Run migration drift test**

Run: `cd backend && source venv/bin/activate && pytest tests/test_migrations.py -q`
Expected: PASS (zero drift — the new migration must cover the `config`/`paused_at` columns).

If drift is detected, run `alembic revision --autogenerate -m "drift fix"` only if a real column is missing; otherwise the autogen-detected differences are the hand-written ones already filtered. Verify the practice migration's `add_column` calls exactly match the model.

- [ ] **Step 3: Update CLAUDE.md**

In the "What exists now" sentence, insert after the taxonomy-admin clause and before the idempotent-seed clause:

```
**practice API** (`/api/practice/sessions` create + scoped delivery + answer judging from snapshot + pause/resume + finish summary with per-domain breakdown + wrong-question list; `/api/practice/questions/{id}/state` bookmarks/flags/notes; service layer `app/services/practice.py` with ValidationError/NotFound/ConflictError → 422/404/409; all gated by `practice:read`),
```

And update the test count from "168 passing" to the new total, and change "What does NOT exist yet" to remove practice and leave "fixed-exam/CAT/analytics/admin UI/interactive import".

- [ ] **Step 4: Commit docs**

```bash
cd /home/john/cissp_exam
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for sub-project E (practice API) completion"
```

- [ ] **Step 5: Finish the development branch**

Announce: "I'm using the finishing-a-development-branch skill to complete this work." Then follow superpowers:finishing-a-development-branch — verify tests, present the 4 options, execute the chosen one (autonomous default per project roadmap: merge to `master` locally and delete the feature branch).

---

## Self-Review

**Spec coverage:**
- FR-PRAC-01 (quick) → Task 2 `subset=all, order=random` default. ✓
- FR-PRAC-02 (domain scope) → Task 2 `_candidate_question_ids` domain_id. ✓
- FR-PRAC-03 (book/chapter scope) → Task 2 book_id + chapter_ids. ✓
- FR-PRAC-05 (custom count) → Task 1 `count` Field(ge=1, le=200). ✓
- FR-PRAC-06 (ordering) → Task 2 random/sequential/easy_to_hard. ✓ (weak_first deferred per spec.)
- FR-PRAC-07 (subsets) → Task 2 `_apply_subset`. ✓
- FR-PRAC-08 (pause/resume) → Task 4. ✓
- FR-PRAC-09 (timing) → Task 3 `time_spent_ms` + elapsed. ✓
- FR-PRAC-10 (summary) → Task 4. ✓
- FR-ANS-01 (one question w/ progress+timing) → Task 3 delivery. ✓
- FR-ANS-02 (judgment) → Task 3 `AnswerResultOut`. ✓
- FR-ANS-03/04 (rationale + per-option) → Task 3 explanation + per_option. ✓
- FR-ANS-05 (mapping + history) → Task 3 `_mapping_out` + `_history_out`. ✓
- FR-ANS-06 (marks) → Task 5. ✓
- FR-ANS-07 (notes) → Task 5 `note`. ✓
- NFR-DATA-01 (snapshots) → Task 3 judges from snapshot. ✓
- NFR-DATA-02 (soft delete) → `not_deleted(Question)`. ✓

**Placeholder scan:** None — every code step contains full code.

**Type consistency:** `create_session`/`get_question_at`/`submit_answer`/`pause_session`/`resume_session`/`finish_session`/`get_summary`/`set_question_state` names match across Tasks 1–6 and the router. `AnswerResultOut.per_option` is a list of dicts in the service return and `PerOptionExplanation` in the schema — Pydantic v2 coerces dicts into the model, so this is consistent. `_load_session` is reused (not renamed) by the router's `get_session` route.
