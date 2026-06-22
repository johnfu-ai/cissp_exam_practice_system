# Fixed Exam API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a fixed-count mock exam API (FR-EXAM-01..06) that assembles questions by CISSP domain weights from the current ExamBlueprint, runs under a timed feedback-free session with lazy auto-submit, and produces a full report + unified review + history — all judged from historical snapshots.

**Architecture:** New service `app/services/exam.py` owns logic+DB; new router `app/api/exam.py` delegates and commits. Reuses existing `ExamSession`/`ExamAnswer` models (one new `config` JSONB column on `ExamSession`), the `snapshot_question()` helper, and the practice/test harness. Routes gated by `exam:read`. Same error mapping as practice (NotFound→404, ValidationError→422, ConflictError→409).

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, PostgreSQL 16 (JSONB, `func.random()`), pytest against `cissp_test`.

## Global Constraints

- Tests run against the `cissp_test` DB (never the dev `cissp` DB); per-test SAVEPOINT rollback. New columns need a model change (auto-applied in tests via `Base.metadata.create_all`) **plus** a migration (for the dev DB + the no-drift test).
- Exam config is **data, not code**: domain weights, item-count bounds, duration, passing/max score come from `ExamBlueprint`/`ExamDomain`. Never hardcode the 100–150 / 3-hour / 700-pass / domain-weight numbers.
- Historical integrity (NFR-DATA-01): judge answers from the snapshot captured at answer time (`snapshot_question()`); review reads per-option `is_correct` and `your_answer.is_correct` from the stored snapshot, never live options.
- The finish endpoint snapshots the scoring basis (`max_score`, `passing_score`, `duration_minutes`) into `ExamSession.config` so later blueprint edits never rescale a past exam.
- Tenant scoping: questions are `organization_id`-scoped; `ExamSession` is tenant-scoped via `TenantScopedMixin`. Taxonomy (`ExamBlueprint`/`ExamDomain`) is GLOBAL.
- Audit via `log_audit(...)` (flushes, does NOT commit); caller commits. Exam mutations use `AuditAction.edit`.
- Do NOT name a route handler `get_session` — it shadows the `from app.db.session import get_session` DB dependency. The detail handler is `get_exam_detail`.
- The uncommitted working-tree edit `M docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` is NOT ours — never stage/commit/discard it. Stage only intended files.
- Current alembic head is `c1c2a4a0c8dc`; the new migration's `down_revision = 'c1c2a4a0c8dc'`.

---

### Task 1: Schemas + ExamSession.config column + migration + stub router

**Files:**
- Create: `backend/app/schemas/exam.py`
- Modify: `backend/app/models/exam.py` (add `config` column to `ExamSession`)
- Create: `backend/app/alembic/versions/d8e1f2a3b4cd_exam_session_config.py`
- Create: `backend/app/services/exam.py` (stub: exceptions + function signatures raising `NotImplementedError`)
- Create: `backend/app/api/exam.py` (stub router, no routes yet)
- Modify: `backend/app/main.py` (register `exam_router`)
- Test: `backend/tests/test_exam_service.py` (column + import smoke)

**Interfaces:**
- Produces: `app/schemas/exam.py` Pydantic models; `app/services/exam.py` with `ValidationError`, `NotFound`, `ConflictError`; `ExamSession.config` JSONB column; migration `d8e1f2a3b4cd`; `exam_router` registered.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_exam_service.py`:

```python
"""Service-layer tests for fixed exam API (sub-project F)."""

import pytest

from app.models.auth import Organization, User
from app.models.enums import (
    OrgKind,
    QuestionStatus,
    QuestionType,
    TextFormat,
)
from app.models.exam import ExamSession
from app.models.question import Question, QuestionOption
from app.services import exam as svc


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


def _question(db_session, org, actor, *, stem="q",
              qtype=QuestionType.single_choice, options=None):
    q = Question(
        organization_id=org.id,
        question_type=qtype,
        stem=stem,
        stem_format=TextFormat.markdown,
        status=QuestionStatus.published,
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


def test_exam_session_has_config_column(db_session):
    """ExamSession must expose a config JSONB column (default '{}')."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    from app.models.enums import ExamSessionKind, ExamSessionStatus
    from app.models.taxonomy import ExamBlueprint

    bp = ExamBlueprint(
        version_label="v1", effective_date="2026-04-15",
        min_items=1, max_items=10, duration_minutes=30,
        passing_score=700, max_score=1000, is_current=True,
    )
    db_session.add(bp)
    db_session.flush()
    es = ExamSession(
        user_id=actor.id, organization_id=org.id, blueprint_id=bp.id,
        session_kind=ExamSessionKind.fixed, total_questions=0,
    )
    db_session.add(es)
    db_session.flush()
    assert es.config == {} or es.config is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source venv/bin/activate && pytest tests/test_exam_service.py::test_exam_session_has_config_column -v`
Expected: FAIL with `AttributeError: 'ExamSession' object has no attribute 'config'` (or import error for `app.services.exam`).

- [ ] **Step 3: Add the `config` column to the model**

In `backend/app/models/exam.py`, add the import and column. Replace the `ExamSession` class body's `ended_at` line with `ended_at` plus a `config` column. Concretely, add to the imports at top:

```python
from sqlalchemy.dialects.postgresql import JSONB
```

Then add this line inside `class ExamSession(...)` immediately after the `ended_at` column definition:

```python
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'")
    )
```

- [ ] **Step 4: Create the schemas**

Create `backend/app/schemas/exam.py`:

```python
"""Pydantic schemas for the fixed exam API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ExamCreateIn(BaseModel):
    count: int | None = Field(default=None, ge=1, le=500)


class ExamSessionOut(BaseModel):
    id: uuid.UUID
    status: str
    session_kind: str
    total_questions: int
    correct_count: int
    started_at: datetime
    ended_at: datetime | None = None
    time_remaining_ms: int | None = None
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
    time_remaining_ms: int
    previous_answer: dict | None = None


class ExamAnswerIn(BaseModel):
    position: int = Field(ge=0)
    selected: list[int]
    started_at: datetime


class ExamAnswerAck(BaseModel):
    position: int
    saved: bool
    time_remaining_ms: int


class DomainPerformance(BaseModel):
    domain_id: uuid.UUID | None
    domain_name: str | None
    weight_pct: int | None
    answered: int
    correct: int
    accuracy: float


class WrongQuestion(BaseModel):
    question_id: uuid.UUID
    stem: str
    selected_indexes: list[int]
    correct_indexes: list[int]


class ExamReportOut(BaseModel):
    session_id: uuid.UUID
    status: str
    total_questions: int
    answered_count: int
    correct_count: int
    scaled_score: int
    max_score: int
    passing_score: int
    passed: bool
    accuracy: float
    total_time_ms: int
    avg_time_ms: float
    domains: list[DomainPerformance]
    wrong_questions: list[WrongQuestion]


class ReviewOption(BaseModel):
    order_index: int
    content: str
    is_correct: bool
    explanation: str | None = None


class ReviewItemOut(BaseModel):
    position: int
    question_id: uuid.UUID
    stem: str
    question_type: str
    options: list[ReviewOption]
    correct_rationale: str | None = None
    key_point_summary: str | None = None
    your_answer: dict | None = None
    time_spent_ms: int | None = None


class ExamHistoryItemOut(BaseModel):
    id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None = None
    status: str
    total_questions: int
    correct_count: int
    scaled_score: int
    max_score: int
    passed: bool
    accuracy: float
```

- [ ] **Step 5: Create the service stub**

Create `backend/app/services/exam.py`:

```python
"""Fixed exam service (sub-project F).

Owns fixed-count exam session creation with domain-weighted auto-assembly
from the current ExamBlueprint, timed feedback-free delivery with lazy
auto-submit, revisable answer submission (judged from snapshot), finish +
report, unified post-exam review, and history/trend.
"""


class ValidationError(ValueError):
    pass


class NotFound(LookupError):
    pass


class ConflictError(ValueError):
    pass


def create_session(session, *, org_id, actor_id, payload):
    raise NotImplementedError


def get_question_at(session, *, session_id, position, user_id):
    raise NotImplementedError


def submit_answer(session, *, session_id, user_id, payload):
    raise NotImplementedError


def finish_session(session, *, session_id, user_id):
    raise NotImplementedError


def get_report(session, *, session_id, user_id):
    raise NotImplementedError


def get_review(session, *, session_id, user_id):
    raise NotImplementedError


def list_history(session, *, user_id):
    raise NotImplementedError
```

- [ ] **Step 6: Create the stub router + register it**

Create `backend/app/api/exam.py`:

```python
"""Fixed exam HTTP API."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/exam", tags=["exam"])
```

In `backend/app/main.py`, add the import (after the `practice_router` import) and the include (after `app.include_router(practice_router)`):

```python
from app.api.exam import router as exam_router
```

```python
    app.include_router(exam_router)
```

- [ ] **Step 7: Create the migration**

Create `backend/app/alembic/versions/d8e1f2a3b4cd_exam_session_config.py`:

```python
"""exam session config

Revision ID: d8e1f2a3b4cd
Revises: c1c2a4a0c8dc
Create Date: 2026-06-23 02:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'd8e1f2a3b4cd'
down_revision = 'c1c2a4a0c8dc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'exam_sessions',
        sa.Column(
            'config',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('exam_sessions', 'config')
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `cd backend && source venv/bin/activate && pytest tests/test_exam_service.py::test_exam_session_has_config_column -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas/exam.py backend/app/models/exam.py \
  backend/app/alembic/versions/d8e1f2a3b4cd_exam_session_config.py \
  backend/app/services/exam.py backend/app/api/exam.py backend/app/main.py \
  backend/tests/test_exam_service.py
git commit -m "feat(exam): schemas + ExamSession.config column + migration + stubs"
```

---

### Task 2: Session creation + domain-weighted assembly

**Files:**
- Modify: `backend/app/services/exam.py` (implement `_current_blueprint`, `_allocate`, `_assemble`, `create_session`)
- Test: `backend/tests/test_exam_service.py` (append assembly tests)

**Interfaces:**
- Consumes: `ExamCreateIn` (from `app/schemas/exam.py`), `ExamBlueprint`/`ExamDomain` (taxonomy), `Question`/`QuestionMapping` (question), `snapshot_question` not needed yet.
- Produces: `create_session(session, *, org_id, actor_id, payload: ExamCreateIn) -> ExamSession` with `config = {count, question_ids: [str...], deadline_at, max_score, passing_score, duration_minutes}`; `status=in_progress`, `session_kind=fixed`, `total_questions=len(question_ids)`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_exam_service.py`:

```python
def _blueprint(db_session, *, current=True, min_items=1, max_items=10,
               duration_minutes=30, passing_score=700, max_score=1000,
               version="v1"):
    from app.models.taxonomy import ExamBlueprint, ExamDomain

    bp = ExamBlueprint(
        version_label=version, effective_date="2026-04-15",
        min_items=min_items, max_items=max_items,
        duration_minutes=duration_minutes, passing_score=passing_score,
        max_score=max_score, is_current=current,
    )
    db_session.add(bp)
    db_session.flush()
    return bp


def _domain(db_session, bp, *, number, name, weight_pct):
    from app.models.taxonomy import ExamDomain

    d = ExamDomain(
        blueprint_id=bp.id, number=number, name=name, weight_pct=weight_pct,
    )
    db_session.add(d)
    db_session.flush()
    return d


def _map(db_session, question, domain=None):
    from app.models.question import QuestionMapping

    m = QuestionMapping(question_id=question.id)
    if domain is not None:
        m.domain_id = domain.id
    db_session.add(m)
    db_session.flush()
    return m


def test_assemble_weights_sum_to_count(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=4, max_items=10)
    d1 = _domain(db_session, bp, number=1, name="D1", weight_pct=50)
    d2 = _domain(db_session, bp, number=2, name="D2", weight_pct=50)
    for i in range(5):
        q = _question(db_session, org, actor, stem=f"a{i}")
        _map(db_session, q, d1 if i < 5 else d2)
    for i in range(5):
        q = _question(db_session, org, actor, stem=f"b{i}")
        _map(db_session, q, d2)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload={"count": 4},
    )
    assert es.total_questions == 4
    assert len(es.config["question_ids"]) == 4
    assert es.config["count"] == 4
    assert es.config["max_score"] == 1000
    assert es.config["passing_score"] == 700
    assert es.config["duration_minutes"] == 30
    assert "deadline_at" in es.config


def test_assemble_redistributes_short_domain(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=4, max_items=10)
    d1 = _domain(db_session, bp, number=1, name="D1", weight_pct=50)
    d2 = _domain(db_session, bp, number=2, name="D2", weight_pct=50)
    # D1 has only 1 question but targets 2 -> shortfall filled from D2.
    q = _question(db_session, org, actor, stem="only1")
    _map(db_session, q, d1)
    for i in range(5):
        q = _question(db_session, org, actor, stem=f"d2-{i}")
        _map(db_session, q, d2)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload={"count": 4},
    )
    assert es.total_questions == 4  # 1 from D1 + 3 from D2


def test_assemble_shortage_rejected(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=1, max_items=10)
    d1 = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    _question(db_session, org, actor, stem="solo")
    # only 1 published question available but count=4
    with pytest.raises(svc.ValidationError):
        svc.create_session(
            db_session, org_id=org.id, actor_id=actor.id,
            payload={"count": 4},
        )


def test_no_current_blueprint_rejected(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _blueprint(db_session, current=False)
    _question(db_session, org, actor)
    with pytest.raises(svc.ValidationError):
        svc.create_session(
            db_session, org_id=org.id, actor_id=actor.id,
            payload={"count": 1},
        )


def test_create_count_clamped_to_bounds(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=5, max_items=8)
    d1 = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    for i in range(10):
        _map(db_session, _question(db_session, org, actor, stem=f"q{i}"), d1)
    # count below min -> clamped up to min_items=5
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"count": 2},
    )
    assert es.total_questions == 5
    # count above max -> clamped down to max_items=8
    es2 = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"count": 99},
    )
    assert es2.total_questions == 8


def test_create_default_count_is_max_items(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=1, max_items=3)
    d1 = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    for i in range(5):
        _map(db_session, _question(db_session, org, actor, stem=f"q{i}"), d1)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={},
    )
    assert es.total_questions == 3  # default = max_items
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_exam_service.py -v -k "assemble or blueprint or clamp or default_count"`
Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement assembly + create_session**

Replace the `create_session` stub in `backend/app/services/exam.py` with a full implementation. Add these imports at the top of the file (after the docstring):

```python
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.queries import not_deleted
from app.models.enums import AuditAction, ExamSessionKind, ExamSessionStatus, QuestionStatus
from app.models.exam import ExamAnswer, ExamSession
from app.models.question import Explanation, Question, QuestionMapping, QuestionOption
from app.models.taxonomy import ExamBlueprint, ExamDomain
from app.schemas.exam import (
    ExamAnswerAck,
    ExamAnswerIn,
    ExamCreateIn,
    ExamHistoryItemOut,
    ExamReportOut,
    ExamSessionOut,
    DomainPerformance,
    QuestionDeliveryOut,
    ReviewItemOut,
    WrongQuestion,
)
from app.services.audit import log_audit
from app.services.snapshot import snapshot_question
```

Then replace the `create_session` stub with:

```python
def _current_blueprint(session: Session) -> ExamBlueprint:
    bp = session.execute(
        select(ExamBlueprint).where(ExamBlueprint.is_current.is_(True))
    ).scalars().first()
    if bp is None:
        raise ValidationError("no current exam blueprint configured")
    return bp


def _allocate(count: int, weights: list[int]) -> list[int]:
    """Largest-remainder allocation: per-domain targets summing exactly to count."""
    raw = [count * w / 100 for w in weights]
    floors = [int(r) for r in raw]
    leftover = count - sum(floors)
    if leftover > 0:
        order = sorted(
            range(len(raw)),
            key=lambda i: raw[i] - floors[i],
            reverse=True,
        )
        for i in range(leftover):
            floors[order[i]] += 1
    return floors


def _domain_question_ids(session: Session, *, org_id, domain_id) -> list[uuid.UUID]:
    return [
        row[0]
        for row in session.execute(
            select(QuestionMapping.question_id)
            .where(
                QuestionMapping.domain_id == domain_id,
                QuestionMapping.question_id.in_(
                    select(Question.id).where(
                        Question.organization_id == org_id,
                        Question.status == QuestionStatus.published,
                        not_deleted(Question),
                    )
                ),
            )
            .order_by(func.random())
        ).all()
    ]


def _assemble(
    session: Session, *, org_id, blueprint: ExamBlueprint, count: int
) -> list[uuid.UUID]:
    domains = list(
        session.execute(
            select(ExamDomain)
            .where(ExamDomain.blueprint_id == blueprint.id)
            .order_by(ExamDomain.number)
        ).scalars().all()
    )
    if not domains:
        raise ValidationError("current blueprint has no domains configured")
    targets = _allocate(count, [d.weight_pct for d in domains])
    pools = {d.id: _domain_question_ids(session, org_id=org_id, domain_id=d.id) for d in domains}
    taken: dict[uuid.UUID, list[uuid.UUID]] = {d.id: [] for d in domains}
    for d, t in zip(domains, targets):
        taken[d.id] = pools[d.id][:t]
    shortfall = count - sum(len(v) for v in taken.values())
    while shortfall > 0:
        progressed = False
        for d in domains:
            if shortfall <= 0:
                break
            have = len(taken[d.id])
            pool = pools[d.id]
            if have < len(pool):
                taken[d.id].append(pool[have])
                shortfall -= 1
                progressed = True
        if not progressed:
            break
    if shortfall > 0:
        raise ValidationError(
            f"not enough published questions to assemble a {count}-question exam"
        )
    all_ids = [qid for d in domains for qid in taken[d.id]]
    random.shuffle(all_ids)
    return all_ids


def create_session(
    session: Session, *, org_id, actor_id, payload: ExamCreateIn
) -> ExamSession:
    bp = _current_blueprint(session)
    count = payload.count if payload.count else bp.max_items
    if count < bp.min_items:
        count = bp.min_items
    if count > bp.max_items:
        count = bp.max_items
    question_ids = _assemble(session, org_id=org_id, blueprint=bp, count=count)
    if not question_ids:
        raise ValidationError(
            f"not enough published questions to assemble a {count}-question exam"
        )
    started = datetime.now(timezone.utc)
    deadline = started + timedelta(minutes=bp.duration_minutes)
    config = {
        "count": len(question_ids),
        "question_ids": [str(q) for q in question_ids],
        "deadline_at": deadline.isoformat(),
        "max_score": bp.max_score,
        "passing_score": bp.passing_score,
        "duration_minutes": bp.duration_minutes,
    }
    es = ExamSession(
        user_id=actor_id,
        organization_id=org_id,
        blueprint_id=bp.id,
        session_kind=ExamSessionKind.fixed,
        status=ExamSessionStatus.in_progress,
        total_questions=len(question_ids),
        correct_count=0,
        config=config,
    )
    session.add(es)
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=actor_id, organization_id=org_id,
        entity_type="exam_session", entity_id=str(es.id),
        details={"total_questions": len(question_ids), "kind": "fixed"},
    )
    return es
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_exam_service.py -v -k "assemble or blueprint or clamp or default_count"`
Expected: PASS (all 6).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/exam.py backend/tests/test_exam_service.py
git commit -m "feat(exam): domain-weighted auto-assembly + session creation"
```

---

### Task 3: Timed delivery + revisable answer submission + lazy auto-submit

**Files:**
- Modify: `backend/app/services/exam.py` (implement `_load_session`, `_deadline`, `_auto_submit_if_expired`, `_options_for`, `get_question_at`, `submit_answer`)
- Test: `backend/tests/test_exam_service.py` (append delivery/answer tests)

**Interfaces:**
- Produces:
  - `get_question_at(session, *, session_id, position, user_id) -> dict` (no `is_correct` in options; includes `time_remaining_ms`, `elapsed_ms`, `previous_answer`).
  - `submit_answer(session, *, session_id, user_id, payload: ExamAnswerIn) -> ExamAnswerAck` (revisable upsert; no judgment returned).
  - `_auto_submit_if_expired(session, es) -> bool` (transitions `in_progress`→`auto_submitted` when `now >= deadline`).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_exam_service.py`:

```python
def _start(db_session, org, actor, *, count=1, bp=None):
    if bp is None:
        bp = _blueprint(db_session, min_items=1, max_items=10)
        d = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
        q = _question(db_session, org, actor, stem="q1")
        _map(db_session, q, d)
    return svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"count": count},
    )


def test_delivery_strips_correctness_and_has_timing(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    s = _start(db_session, org, actor, count=1)
    out = svc.get_question_at(
        db_session, session_id=s.id, position=0, user_id=actor.id
    )
    assert out["position"] == 0
    assert out["total"] == 1
    assert out["stem"] == "q1"
    for opt in out["options"]:
        assert "is_correct" not in opt
    assert out["time_remaining_ms"] > 0
    assert out["elapsed_ms"] >= 0
    assert out["previous_answer"] is None


def test_submit_answer_returns_ack_no_judgment(db_session):
    from datetime import datetime, timezone

    org = _org(db_session)
    actor = _actor(db_session, org)
    s = _start(db_session, org, actor, count=1)
    ack = svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    assert ack["saved"] is True
    assert ack["position"] == 0
    assert "is_correct" not in ack
    assert ack["time_remaining_ms"] > 0


def test_answer_is_revisable_single_row(db_session):
    from datetime import datetime, timezone

    from app.models.exam import ExamAnswer

    org = _org(db_session)
    actor = _actor(db_session, org)
    s = _start(db_session, org, actor, count=1)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [1],
                 "started_at": datetime.now(timezone.utc)},
    )
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    rows = db_session.query(ExamAnswer).filter_by(session_id=s.id).all()
    assert len(rows) == 1
    assert rows[0].user_answer == {"selected": [0]}
    assert rows[0].is_correct is True  # judged from snapshot at revise time


def test_answer_persists_snapshot(db_session):
    from datetime import datetime, timezone

    from app.models.exam import ExamAnswer

    org = _org(db_session)
    actor = _actor(db_session, org)
    s = _start(db_session, org, actor, count=1)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    ans = db_session.query(ExamAnswer).filter_by(session_id=s.id).one()
    assert ans.question_snapshot["options"][0]["is_correct"] is True
    assert ans.is_correct is True


def test_delivery_returns_previous_answer(db_session):
    from datetime import datetime, timezone

    org = _org(db_session)
    actor = _actor(db_session, org)
    s = _start(db_session, org, actor, count=1)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [1],
                 "started_at": datetime.now(timezone.utc)},
    )
    out = svc.get_question_at(
        db_session, session_id=s.id, position=0, user_id=actor.id
    )
    assert out["previous_answer"] == {"selected": [1]}


def test_lazy_auto_submit_after_deadline(db_session):
    from datetime import datetime, timezone

    from app.models.enums import ExamSessionStatus

    org = _org(db_session)
    actor = _actor(db_session, org)
    s = _start(db_session, org, actor, count=1)
    # Force the deadline into the past.
    s.config["deadline_at"] = (datetime.now(timezone.utc)).isoformat()
    db_session.flush()
    with pytest.raises(svc.ConflictError):
        svc.get_question_at(
            db_session, session_id=s.id, position=0, user_id=actor.id
        )
    assert db_session.get(ExamSession, s.id).status == ExamSessionStatus.auto_submitted


def test_position_out_of_range_rejected(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    s = _start(db_session, org, actor, count=1)
    with pytest.raises(svc.ValidationError):
        svc.get_question_at(
            db_session, session_id=s.id, position=5, user_id=actor.id
        )


def test_other_user_exam_not_found(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    intruder = _actor(db_session, org, email="other@example.com")
    s = _start(db_session, org, actor, count=1)
    with pytest.raises(svc.NotFound):
        svc.get_question_at(
            db_session, session_id=s.id, position=0, user_id=intruder.id
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_exam_service.py -v -k "delivery or submit_answer or revisable or persists_snapshot or previous_answer or auto_submit or out_of_range or other_user"`
Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement delivery + answer + auto-submit**

Replace the `get_question_at` and `submit_answer` stubs in `backend/app/services/exam.py` with:

```python
def _load_session(session: Session, session_id, user_id) -> ExamSession:
    es = session.get(ExamSession, session_id)
    if es is None or es.user_id != user_id:
        raise NotFound(f"exam session {session_id} not found")
    return es


def _deadline(es: ExamSession) -> datetime:
    val = es.config.get("deadline_at")
    dl = datetime.fromisoformat(val)
    if dl.tzinfo is None:
        dl = dl.replace(tzinfo=timezone.utc)
    return dl


def _time_remaining_ms(es: ExamSession) -> int:
    return max(0, int((_deadline(es) - datetime.now(timezone.utc)).total_seconds() * 1000))


def _auto_submit_if_expired(session: Session, es: ExamSession) -> bool:
    if es.status != ExamSessionStatus.in_progress:
        return False
    if datetime.now(timezone.utc) < _deadline(es):
        return False
    es.status = ExamSessionStatus.auto_submitted
    es.ended_at = _deadline(es)
    session.flush()
    return True


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
    es = _load_session(session, session_id, user_id)
    if _auto_submit_if_expired(session, es) or es.status != ExamSessionStatus.in_progress:
        raise ConflictError("exam session is not in progress")
    qids = es.config.get("question_ids", [])
    if position < 0 or position >= len(qids):
        raise ValidationError("position out of range")
    question = session.get(Question, uuid.UUID(qids[position]))
    if question is None or question.deleted_at is not None:
        raise NotFound("question no longer available")
    options = _options_for(session, question.id)
    started = es.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    elapsed_ms = int(
        (datetime.now(timezone.utc) - started).total_seconds() * 1000
    )
    prev = session.execute(
        select(ExamAnswer).where(
            ExamAnswer.session_id == es.id,
            ExamAnswer.question_id == question.id,
        )
    ).scalars().first()
    return {
        "session_id": str(es.id),
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
        "time_remaining_ms": _time_remaining_ms(es),
        "previous_answer": (
            {"selected": prev.user_answer.get("selected")} if prev else None
        ),
    }


def _judge(snapshot: dict, selected: list[int]) -> bool:
    correct_indexes = [o["order_index"] for o in snapshot["options"] if o["is_correct"]]
    return set(selected) == set(correct_indexes)


def submit_answer(
    session: Session, *, session_id, user_id, payload: ExamAnswerIn
) -> ExamAnswerAck:
    es = _load_session(session, session_id, user_id)
    if _auto_submit_if_expired(session, es) or es.status != ExamSessionStatus.in_progress:
        raise ConflictError("exam session is not in progress")
    qids = es.config.get("question_ids", [])
    if payload.position < 0 or payload.position >= len(qids):
        raise ValidationError("position out of range")
    question_id = uuid.UUID(qids[payload.position])
    question = session.get(Question, question_id)
    if question is None or question.deleted_at is not None:
        raise NotFound("question no longer available")
    options = _options_for(session, question_id)
    snap = snapshot_question(question, options)
    is_correct = _judge(snap, payload.selected)
    now = datetime.now(timezone.utc)
    started = payload.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    time_spent_ms = max(0, int((now - started).total_seconds() * 1000))
    existing = session.execute(
        select(ExamAnswer).where(
            ExamAnswer.session_id == es.id,
            ExamAnswer.question_id == question_id,
        )
    ).scalars().first()
    if existing is None:
        existing = ExamAnswer(
            session_id=es.id, user_id=user_id, question_id=question_id,
        )
        session.add(existing)
    existing.question_snapshot = snap
    existing.options_snapshot = snap["options"]
    existing.user_answer = {"selected": payload.selected}
    existing.is_correct = is_correct
    existing.time_spent_ms = time_spent_ms
    existing.answered_at = now
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=user_id,
        organization_id=es.organization_id, entity_type="exam_answer",
        entity_id=str(existing.id), details={"is_correct": is_correct},
    )
    return ExamAnswerAck(
        position=payload.position, saved=True,
        time_remaining_ms=_time_remaining_ms(es),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_exam_service.py -v -k "delivery or submit_answer or revisable or persists_snapshot or previous_answer or auto_submit or out_of_range or other_user"`
Expected: PASS (all 8).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/exam.py backend/tests/test_exam_service.py
git commit -m "feat(exam): timed delivery + revisable answers + lazy auto-submit"
```

---

### Task 4: Finish + report (scaled score, pass, domains, wrong questions)

**Files:**
- Modify: `backend/app/services/exam.py` (implement `finish_session`, `_build_report`, `get_report`)
- Test: `backend/tests/test_exam_service.py` (append finish/report tests)

**Interfaces:**
- Produces:
  - `finish_session(session, *, session_id, user_id) -> ExamReportOut` (recomputes `correct_count`, sets `completed`/`ended_at` if manual).
  - `get_report(session, *, session_id, user_id) -> ExamReportOut`.
  - `_build_report(session, es) -> ExamReportOut`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_exam_service.py`:

```python
def _two_question_exam(db_session, *, passing_score=700, max_score=1000):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(
        db_session, min_items=2, max_items=2, passing_score=passing_score,
        max_score=max_score,
    )
    d = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    q1 = _question(db_session, org, actor, stem="right")  # option 0 correct
    q2 = _question(db_session, org, actor, stem="wrong")  # option 0 correct
    _map(db_session, q1, d)
    _map(db_session, q2, d)
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"count": 2},
    )
    return org, actor, s, (q1, q2)


def test_finish_recomputes_correct_count_and_score(db_session):
    from datetime import datetime, timezone

    org, actor, s, (q1, q2) = _two_question_exam(db_session)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 1, "selected": [1],
                 "started_at": datetime.now(timezone.utc)},
    )
    report = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert report.total_questions == 2
    assert report.answered_count == 2
    assert report.correct_count == 1
    # 1/2 * 1000 = 500
    assert report.scaled_score == 500
    assert report.max_score == 1000
    assert report.passing_score == 700
    assert report.passed is False
    assert report.accuracy == 0.5
    assert len(report.wrong_questions) == 1
    assert report.wrong_questions[0].question_id == q2.id
    assert report.wrong_questions[0].correct_indexes == [0]
    assert report.wrong_questions[0].selected_indexes == [1]


def test_finish_per_domain_performance(db_session):
    from datetime import datetime, timezone

    org, actor, s, _ = _two_question_exam(db_session)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 1, "selected": [1],
                 "started_at": datetime.now(timezone.utc)},
    )
    report = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert len(report.domains) == 1
    assert report.domains[0].answered == 2
    assert report.domains[0].correct == 1
    assert report.domains[0].accuracy == 0.5


def test_finish_passing_line(db_session):
    from datetime import datetime, timezone

    org, actor, s, _ = _two_question_exam(db_session, passing_score=0, max_score=1000)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    report = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert report.passed is True  # 500 >= 0


def test_finish_recomputes_after_revision(db_session):
    from datetime import datetime, timezone

    org, actor, s, _ = _two_question_exam(db_session)
    # answer both wrong first
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [1],
                 "started_at": datetime.now(timezone.utc)},
    )
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 1, "selected": [1],
                 "started_at": datetime.now(timezone.utc)},
    )
    # revise position 0 to correct
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    report = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert report.correct_count == 1  # only the revised answer counts


def test_finish_idempotent(db_session):
    from datetime import datetime, timezone

    from app.models.enums import ExamSessionStatus

    org, actor, s, _ = _two_question_exam(db_session)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    a = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    b = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert a.correct_count == b.correct_count
    assert db_session.get(ExamSession, s.id).status == ExamSessionStatus.completed


def test_get_report_after_finish(db_session):
    from datetime import datetime, timezone

    org, actor, s, _ = _two_question_exam(db_session)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    report = svc.get_report(db_session, session_id=s.id, user_id=actor.id)
    assert report.correct_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_exam_service.py -v -k "finish or get_report"`
Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement finish + report**

Replace the `finish_session` and `get_report` stubs in `backend/app/services/exam.py` with:

```python
def _build_report(session: Session, es: ExamSession) -> ExamReportOut:
    answers = list(
        session.execute(
            select(ExamAnswer).where(ExamAnswer.session_id == es.id)
        ).scalars().all()
    )
    correct = sum(1 for a in answers if a.is_correct)
    answered = len(answers)
    total = es.total_questions or 0
    max_score = es.config.get("max_score", 0)
    passing_score = es.config.get("passing_score", 0)
    scaled_score = round((correct / total) * max_score) if total else 0
    passed = scaled_score >= passing_score
    accuracy = (correct / total) if total else 0.0
    total_time = sum((a.time_spent_ms or 0) for a in answers)
    avg_time = (total_time / answered) if answered else 0.0

    # Per-domain grouping.
    domain_stats: dict = {}
    for a in answers:
        m = session.execute(
            select(QuestionMapping).where(QuestionMapping.question_id == a.question_id)
        ).scalars().first()
        did = str(m.domain_id) if (m and m.domain_id) else None
        entry = domain_stats.setdefault(
            did, {"answered": 0, "correct": 0, "weight_pct": None, "name": None}
        )
        entry["answered"] += 1
        if a.is_correct:
            entry["correct"] += 1
    for did, entry in domain_stats.items():
        if did is not None:
            d = session.get(ExamDomain, uuid.UUID(did))
            if d is not None:
                entry["name"] = d.name
                entry["weight_pct"] = d.weight_pct

    wrong = [
        WrongQuestion(
            question_id=uuid.UUID(a.question_snapshot.get("question_id")) if a.question_snapshot.get("question_id") else a.question_id,
            stem=a.question_snapshot.get("stem", ""),
            selected_indexes=(a.user_answer or {}).get("selected", []),
            correct_indexes=[
                o["order_index"] for o in a.options_snapshot if o["is_correct"]
            ],
        )
        for a in answers if not a.is_correct
    ]
    return ExamReportOut(
        session_id=es.id,
        status=es.status.value,
        total_questions=total,
        answered_count=answered,
        correct_count=correct,
        scaled_score=scaled_score,
        max_score=max_score,
        passing_score=passing_score,
        passed=passed,
        accuracy=accuracy,
        total_time_ms=total_time,
        avg_time_ms=avg_time,
        domains=[
            DomainPerformance(
                domain_id=uuid.UUID(did) if did else None,
                domain_name=entry["name"],
                weight_pct=entry["weight_pct"],
                answered=entry["answered"],
                correct=entry["correct"],
                accuracy=(entry["correct"] / entry["answered"]) if entry["answered"] else 0.0,
            )
            for did, entry in domain_stats.items()
        ],
        wrong_questions=wrong,
    )


def finish_session(session: Session, *, session_id, user_id) -> ExamReportOut:
    es = _load_session(session, session_id, user_id)
    _auto_submit_if_expired(session, es)
    if es.status == ExamSessionStatus.in_progress:
        es.status = ExamSessionStatus.completed
        es.ended_at = datetime.now(timezone.utc)
        session.flush()
        log_audit(
            session, action=AuditAction.edit, actor_id=user_id,
            organization_id=es.organization_id, entity_type="exam_session",
            entity_id=str(es.id), details={"finished": True, "auto": False},
        )
    answers = list(
        session.execute(
            select(ExamAnswer).where(ExamAnswer.session_id == es.id)
        ).scalars().all()
    )
    es.correct_count = sum(1 for a in answers if a.is_correct)
    session.flush()
    return _build_report(session, es)


def get_report(session: Session, *, session_id, user_id) -> ExamReportOut:
    es = _load_session(session, session_id, user_id)
    if es.status == ExamSessionStatus.in_progress:
        raise ConflictError("exam session is not finished")
    return _build_report(session, es)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_exam_service.py -v -k "finish or get_report"`
Expected: PASS (all 6).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/exam.py backend/tests/test_exam_service.py
git commit -m "feat(exam): finish + report (scaled score/pass/domains/wrong questions)"
```

---

### Task 5: Unified review + history/trend (historical scoring basis)

**Files:**
- Modify: `backend/app/services/exam.py` (implement `get_review`, `list_history`)
- Test: `backend/tests/test_exam_service.py` (append review/history tests)

**Interfaces:**
- Produces:
  - `get_review(session, *, session_id, user_id) -> list[ReviewItemOut]` (only after finish; reads correctness from snapshot).
  - `list_history(session, *, user_id) -> list[ExamHistoryItemOut]` (only completed/auto_submitted, ordered by `started_at` asc; scoring from `config` basis).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_exam_service.py`:

```python
def test_review_only_after_finish(db_session):
    from datetime import datetime, timezone

    org, actor, s, _ = _two_question_exam(db_session)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    with pytest.raises(svc.ConflictError):
        svc.get_review(db_session, session_id=s.id, user_id=actor.id)
    svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    review = svc.get_review(db_session, session_id=s.id, user_id=actor.id)
    assert len(review) == 2
    assert review[0].position == 0
    assert review[0].your_answer["is_correct"] is True
    # options expose is_correct (from snapshot)
    assert any(o.is_correct for o in review[0].options)


def test_review_reads_correctness_from_snapshot(db_session):
    from datetime import datetime, timezone

    from app.models.question import QuestionOption

    org, actor, s, (q1, q2) = _two_question_exam(db_session)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    # Mutate the live question so option 0 is now WRONG and option 1 is RIGHT.
    opt0 = db_session.query(QuestionOption).filter_by(
        question_id=q1.id, order_index=0).one()
    opt1 = db_session.query(QuestionOption).filter_by(
        question_id=q1.id, order_index=1).one()
    opt0.is_correct = False
    opt1.is_correct = True
    db_session.flush()
    svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    review = svc.get_review(db_session, session_id=s.id, user_id=actor.id)
    item0 = review[0]
    # snapshot still says order_index 0 was correct
    assert item0.options[0].is_correct is True
    assert item0.options[1].is_correct is False
    # the answer was judged correct against the original snapshot
    assert item0.your_answer["is_correct"] is True


def test_history_ordered_and_only_finished(db_session):
    from datetime import datetime, timezone

    org = _org(db_session)
    actor = _actor(db_session, org)
    # first exam: 1 question, finished
    bp1 = _blueprint(db_session, min_items=1, max_items=1, version="v1")
    d1 = _domain(db_session, bp1, number=1, name="D1", weight_pct=100)
    q = _question(db_session, org, actor, stem="q")
    _map(db_session, q, d1)
    s1 = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"count": 1})
    svc.submit_answer(
        db_session, session_id=s1.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)})
    svc.finish_session(db_session, session_id=s1.id, user_id=actor.id)
    # second exam: in progress (should NOT appear)
    s2 = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"count": 1})
    hist = svc.list_history(db_session, user_id=actor.id)
    assert len(hist) == 1
    assert hist[0].id == s1.id
    assert hist[0].scaled_score == 1000
    assert hist[0].passed is True


def test_history_uses_historical_scoring_basis(db_session):
    from datetime import datetime, timezone

    from app.models.taxonomy import ExamBlueprint

    org, actor, s, _ = _two_question_exam(
        db_session, passing_score=700, max_score=1000)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)})
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 1, "selected": [1],
                 "started_at": datetime.now(timezone.utc)})
    svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    # Now raise the blueprint's passing score to 600 -> 500 < 600 still fail,
    # but lower it to 0 -> would pass if recomputed. Confirm config basis holds.
    bp = db_session.get(ExamBlueprint, s.blueprint_id)
    bp.passing_score = 0  # if history recomputed, passed would flip to True
    db_session.flush()
    hist = svc.list_history(db_session, user_id=actor.id)
    assert hist[0].passed is False  # still judged against original 700 (config basis)
    # scaled 500 (1/2 * 1000) is unchanged; only the basis in config matters.
    assert hist[0].scaled_score == 500
```

> Note: `ExamHistoryItemOut` exposes `max_score` (from `config`) but not `passing_score`; the
> historical-basis guarantee is proven by `passed` staying `False` (500 < 700) even though the
> live blueprint's `passing_score` is now 0 (which would make 500 pass if recomputed).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_exam_service.py -v -k "review or history"`
Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement review + history**

Replace the `get_review` and `list_history` stubs in `backend/app/services/exam.py` with:

```python
def get_review(session: Session, *, session_id, user_id) -> list:
    es = _load_session(session, session_id, user_id)
    if es.status == ExamSessionStatus.in_progress:
        raise ConflictError("exam session is not finished")
    qids = es.config.get("question_ids", [])
    items: list = []
    for position, qid_str in enumerate(qids):
        question_id = uuid.UUID(qid_str)
        question = session.get(Question, question_id)
        ans = session.execute(
            select(ExamAnswer).where(
                ExamAnswer.session_id == es.id,
                ExamAnswer.question_id == question_id,
            )
        ).scalars().first()
        explanation = session.execute(
            select(Explanation).where(Explanation.question_id == question_id)
        ).scalars().first()
        # Per-option correctness + content come from the stored snapshot
        # (NFR-DATA-01): later edits to live options never change the review.
        if ans is not None and ans.options_snapshot:
            opts = [
                {
                    "order_index": o["order_index"],
                    "content": o["content"],
                    "is_correct": o["is_correct"],
                    "explanation": None,
                }
                for o in ans.options_snapshot
            ]
            stem = ans.question_snapshot.get("stem", question.stem if question else "")
            qtype = ans.question_snapshot.get("question_type", "")
        else:
            # Never answered: fall back to live question for stem/options.
            live_opts = _options_for(session, question_id) if question else []
            opts = [
                {
                    "order_index": o.order_index,
                    "content": o.content,
                    "is_correct": o.is_correct,
                    "explanation": o.explanation,
                }
                for o in live_opts
            ]
            stem = question.stem if question else ""
            qtype = question.question_type.value if question else ""
        items.append(
            ReviewItemOut(
                position=position,
                question_id=question_id,
                stem=stem,
                question_type=qtype,
                options=opts,
                correct_rationale=(
                    explanation.correct_answer_rationale if explanation else None
                ),
                key_point_summary=(
                    explanation.key_point_summary if explanation else None
                ),
                your_answer=(
                    {
                        "selected": ans.user_answer.get("selected"),
                        "is_correct": ans.is_correct,
                    }
                    if ans
                    else None
                ),
                time_spent_ms=ans.time_spent_ms if ans else None,
            )
        )
    return items


def _scaled(es: ExamSession) -> tuple[int, bool, float]:
    total = es.total_questions or 0
    max_score = es.config.get("max_score", 0)
    passing_score = es.config.get("passing_score", 0)
    scaled = round((es.correct_count / total) * max_score) if total else 0
    passed = scaled >= passing_score
    accuracy = (es.correct_count / total) if total else 0.0
    return scaled, passed, accuracy


def list_history(session: Session, *, user_id) -> list:
    rows = list(
        session.execute(
            select(ExamSession).where(
                ExamSession.user_id == user_id,
                ExamSession.status.in_([
                    ExamSessionStatus.completed,
                    ExamSessionStatus.auto_submitted,
                ]),
            ).order_by(ExamSession.started_at.asc())
        ).scalars().all()
    )
    out: list = []
    for es in rows:
        scaled, passed, accuracy = _scaled(es)
        out.append(
            ExamHistoryItemOut(
                id=es.id,
                started_at=es.started_at,
                ended_at=es.ended_at,
                status=es.status.value,
                total_questions=es.total_questions,
                correct_count=es.correct_count,
                scaled_score=scaled,
                max_score=es.config.get("max_score", 0),
                passed=passed,
                accuracy=accuracy,
            )
        )
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_exam_service.py -v -k "review or history"`
Expected: PASS (all 4).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/exam.py backend/tests/test_exam_service.py
git commit -m "feat(exam): unified review (snapshot-graded) + history/trend"
```

---

### Task 6: HTTP router

**Files:**
- Modify: `backend/app/api/exam.py` (wire all 8 routes)
- Test: `backend/tests/test_exam_api.py` (create)

**Interfaces:**
- Consumes: all `app/services/exam.py` functions; `app/schemas/exam.py` models; `require_permission("exam:read")`; `get_session` DB dependency.
- Produces: `POST /api/exam/sessions`, `GET /api/exam/sessions/{id}`, `GET /api/exam/sessions/{id}/questions/{position}`, `POST /api/exam/sessions/{id}/answers`, `POST /api/exam/sessions/{id}/finish`, `GET /api/exam/sessions/{id}/report`, `GET /api/exam/sessions/{id}/review`, `GET /api/exam/history`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_exam_api.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_exam_api.py -v`
Expected: FAIL (404s / no routes).

- [ ] **Step 3: Wire the router**

Replace the contents of `backend/app/api/exam.py` with:

```python
"""Fixed exam HTTP API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dependencies import CurrentUser, require_permission
from app.schemas.exam import (
    ExamAnswerAck,
    ExamAnswerIn,
    ExamCreateIn,
    ExamReportOut,
    ExamSessionOut,
    QuestionDeliveryOut,
    ReviewItemOut,
)
from app.services import exam as svc

router = APIRouter(prefix="/api/exam", tags=["exam"])


def _session_out(es) -> ExamSessionOut:
    remaining = None
    if es.status.value == "in_progress":
        try:
            from datetime import datetime, timezone
            dl = datetime.fromisoformat(es.config.get("deadline_at"))
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            remaining = max(0, int((dl - datetime.now(timezone.utc)).total_seconds() * 1000))
        except Exception:
            remaining = None
    # Strip the full question_ids list from the public config.
    safe_config = {k: v for k, v in (es.config or {}).items() if k != "question_ids"}
    return ExamSessionOut(
        id=es.id, status=es.status.value, session_kind=es.session_kind.value,
        total_questions=es.total_questions, correct_count=es.correct_count,
        started_at=es.started_at, ended_at=es.ended_at,
        time_remaining_ms=remaining, config=safe_config,
    )


@router.post("/sessions", response_model=ExamSessionOut)
def create_exam(
    body: ExamCreateIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    try:
        es = svc.create_session(
            session, org_id=current.org_id, actor_id=current.user.id, payload=body
        )
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(es)
    return _session_out(es)


@router.get("/sessions/{session_id}", response_model=ExamSessionOut)
def get_exam_detail(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    try:
        es = svc._load_session(session, session_id, current.user.id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="exam session not found")
    return _session_out(es)


@router.get("/sessions/{session_id}/questions/{position}", response_model=QuestionDeliveryOut)
def get_exam_question(
    session_id: uuid.UUID,
    position: int,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    try:
        return svc.get_question_at(
            session, session_id=session_id, position=position, user_id=current.user.id
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session or question not found")
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/sessions/{session_id}/answers", response_model=ExamAnswerAck)
def submit_exam_answer(
    session_id: uuid.UUID,
    body: ExamAnswerIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    try:
        ack = svc.submit_answer(
            session, session_id=session_id, user_id=current.user.id, payload=body
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session or question not found")
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return ack


@router.post("/sessions/{session_id}/finish", response_model=ExamReportOut)
def finish_exam(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    try:
        report = svc.finish_session(
            session, session_id=session_id, user_id=current.user.id
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="exam session not found")
    session.commit()
    return report


@router.get("/sessions/{session_id}/report", response_model=ExamReportOut)
def get_exam_report(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    try:
        return svc.get_report(session, session_id=session_id, user_id=current.user.id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="exam session not found")
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/sessions/{session_id}/review", response_model=list[ReviewItemOut])
def get_exam_review(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    try:
        return svc.get_review(session, session_id=session_id, user_id=current.user.id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="exam session not found")
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/history")
def list_exam_history(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    return svc.list_history(session, user_id=current.user.id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_exam_api.py -v`
Expected: PASS (all 5).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/exam.py backend/tests/test_exam_api.py
git commit -m "feat(exam): HTTP router (/api/exam) + registration"
```

---

### Task 7: Full suite + migration drift + docs + finish branch

**Files:**
- Modify: `CLAUDE.md` (mark fixed-exam API done, bump test count, update NOT-exist list)
- Modify: `backend/app/services/exam.py` (remove any leftover `NotImplementedError` stubs for `get_report`/`get_review`/`list_history` if still present — they are implemented in Tasks 4–5; verify none remain)

**Interfaces:**
- Produces: a green full backend suite, zero migration drift, updated docs, and a finished branch ready to merge to `master`.

- [ ] **Step 1: Run the full backend suite**

Run: `cd backend && source venv/bin/activate && pytest -q`
Expected: all pass (previous 191 + new exam service + exam API tests). Record the count.

- [ ] **Step 2: Run the migration drift test**

Run: `cd backend && source venv/bin/activate && pytest tests/test_migrations.py -q`
Expected: PASS (zero drift). The new `config` column on `exam_sessions` is covered by migration `d8e1f2a3b4cd`.

- [ ] **Step 3: Apply the migration to the dev DB (smoke)**

Run: `cd backend && source venv/bin/activate && alembic upgrade head`
Expected: upgrades to `d8e1f2a3b4cd` cleanly.

- [ ] **Step 4: Update CLAUDE.md**

In `CLAUDE.md`, in the "What exists now" sentence, append after the practice-API clause a new clause:

```
, **fixed exam API** (`/api/exam/sessions` create with domain-weighted auto-assembly from the current ExamBlueprint, timed feedback-free delivery with lazy auto-submit, revisable answers judged from snapshot, `/api/exam/sessions/{id}/finish` + `/report` (scaled score/pass/accuracy/per-domain/time/wrong-question list), `/api/exam/sessions/{id}/review` unified post-exam review, `/api/exam/history` trend)
```

Update the test count in the same paragraph ("122 passing" → the new total from Step 1, e.g. "21N passing").

In the "What does NOT exist yet" list, change "fixed-exam/CAT APIs, analytics & admin UI, interactive import" to "CAT API, analytics & admin UI, interactive import".

- [ ] **Step 5: Commit docs**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for sub-project F (fixed exam API)"
```

- [ ] **Step 6: Finish the development branch**

Announce: "I'm using the finishing-a-development-branch skill to complete this work." Run the full suite once more to confirm green, then merge `feat/fixed-exam-api` to `master` locally (Option 1), run tests on the merged result, delete the feature branch. Do NOT touch the uncommitted `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` edit.

- [ ] **Step 7: Update the roadmap memory**

After merge, update `/home/john/.claude/projects/-home-john-cissp-exam/memory/cissp-project-roadmap.md`: mark F as DONE (merged to master 2026-06-23) with the feature list, the migration id `d8e1f2a3b4cd`, the final test count, and the gotcha "exam answers are revisable (upsert) — unlike practice which is one-shot; `correct_count` is recomputed at finish." Reaffirm G (CAT) and H (Analytics & admin) as next.
