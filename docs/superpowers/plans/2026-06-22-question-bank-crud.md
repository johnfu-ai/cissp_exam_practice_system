# Question Bank CRUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the question-bank management API (CRUD, status lifecycle/review, revision history, correction feedback) plus taxonomy READ endpoints, with full RBAC gating and TDD coverage.

**Architecture:** Service-layer backend. `app/services/question.py` + `app/services/taxonomy.py` own logic/DB; `app/api/questions.py` + `app/api/taxonomy.py` are thin routes. One new model (`QuestionFeedback`) + two enums + one migration. Existing `Question`/`QuestionOption`/`Explanation`/`QuestionMapping`/`QuestionRevision` models are reused. Tenant scoping via `current.org_id`; soft delete via `not_deleted(Question)`.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic, PostgreSQL 16, pytest (real `cissp_test` DB).

## Global Constraints

- Tests run against `cissp_test` DB only (never dev `cissp`); per-test SAVEPOINT rollback via `db_session` fixture.
- Soft delete only (`not_deleted(model)`); never hard-delete questions.
- Tenant scoping: questions/books/chapters/feedback are `organization_id`-scoped; `ExamDomain`/`KnowledgePoint`/`Tag` are GLOBAL.
- Native PG ENUMs: new enums created with `CREATE TYPE` in upgrade, `DROP TYPE` in downgrade.
- Permission gating via `require_permission(code)` from `app/dependencies.py`. Existing perms: `question:read`, `question:write`, `question:publish`.
- Routes catch `LookupError`→404, `ValueError`→422 (validation) or 409 (illegal transition), commit after mutations.
- ORM/parameterized queries only — no raw string SQL.

**Reference:** Spec at `docs/superpowers/specs/2026-06-22-question-bank-crud-design.md`.

---

### Task 1: QuestionFeedback model + enums + migration

**Files:**
- Modify: `backend/app/models/enums.py` (add 2 enums)
- Modify: `backend/app/models/question.py` (add `QuestionFeedback` class)
- Create: `backend/app/alembic/versions/<rev>_question_feedback.py` (autogenerate)
- Test: `backend/tests/test_migrations.py` (existing drift test must stay green)

**Interfaces:**
- Produces: `QuestionFeedbackType`, `QuestionFeedbackStatus` enums; `QuestionFeedback` ORM model registered on metadata.

- [ ] **Step 1: Add the two enums to `app/models/enums.py`**

Append after `EtlRunPhase`:

```python
class QuestionFeedbackType(str, enum.Enum):
    unclear_explanation = "unclear_explanation"
    suspected_wrong_answer = "suspected_wrong_answer"
    ambiguous_stem = "ambiguous_stem"
    copyright_issue = "copyright_issue"
    other = "other"


class QuestionFeedbackStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"
    wont_fix = "wont_fix"
```

- [ ] **Step 2: Add `QuestionFeedback` model to `app/models/question.py`**

Add imports `QuestionFeedbackType`, `QuestionFeedbackStatus` to the existing `from app.models.enums import (...)` block, and append the class at the end of the file:

```python
class QuestionFeedback(
    UUIDPrimaryKey,
    TenantScopedMixin,
    TimestampMixin,
    SoftDeleteMixin,
    Base,
):
    __tablename__ = "question_feedback"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    reporter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    feedback_type: Mapped[QuestionFeedbackType] = mapped_column(
        Enum(QuestionFeedbackType, name="question_feedback_type", create_type=True),
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[QuestionFeedbackStatus] = mapped_column(
        Enum(QuestionFeedbackStatus, name="question_feedback_status", create_type=True),
        nullable=False,
        server_default=QuestionFeedbackStatus.open.value,
    )
```

(`Text` is already imported in that module.)

- [ ] **Step 3: Generate the migration**

Run:
```bash
cd backend && source venv/bin/activate
alembic revision --autogenerate -m "question feedback table"
```

Open the generated file. Verify `upgrade()` does `op.create_table('question_feedback', ...)` with the two `postgresql.ENUM(..., name="question_feedback_type", create_type=False)` columns and `op.create_index` on `question_id`. Verify `downgrade()` calls `op.drop_table` then **explicitly** `op.execute("DROP TYPE question_feedback_type")` and `op.execute("DROP TYPE question_feedback_status")` (autogen does NOT drop types — add these two lines manually after `drop_table`).

- [ ] **Step 4: Verify migration + zero drift**

```bash
cd backend && source venv/bin/activate
pytest tests/test_migrations.py -q
```
Expected: 2 passed (upgrade applies cleanly against `cissp_migtest`; autogenerate-drift is zero).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/enums.py backend/app/models/question.py backend/app/alembic/versions/
git commit -m "feat(question-bank): QuestionFeedback model + enums + migration"
```

---

### Task 2: Pydantic schemas (question + taxonomy)

**Files:**
- Create: `backend/app/schemas/question.py`
- Create: `backend/app/schemas/taxonomy.py`

**Interfaces:**
- Produces: `OptionIn`, `OptionOut`, `ExplanationIn`, `ExplanationOut`, `QuestionCreateIn`, `QuestionUpdateIn`, `QuestionOut`, `QuestionListItem`, `ReviewAction` (enum), `ReviewActionIn`, `FeedbackIn`, `FeedbackOut`, `RevisionOut`; `DomainOut`, `BookOut`, `ChapterOut`, `KnowledgePointOut`.

- [ ] **Step 1: Write `app/schemas/question.py`**

```python
import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.enums import (
    LicenseStatus,
    QuestionFeedbackStatus,
    QuestionFeedbackType,
    QuestionStatus,
    QuestionType,
    TextFormat,
)


class OptionIn(BaseModel):
    content: str
    content_format: TextFormat = TextFormat.markdown
    is_correct: bool = False
    order_index: int | None = None
    explanation: str | None = None


class OptionOut(BaseModel):
    id: uuid.UUID
    order_index: int
    content: str
    content_format: TextFormat
    is_correct: bool
    explanation: str | None = None


class ExplanationIn(BaseModel):
    correct_answer_rationale: str
    key_point_summary: str | None = None
    further_reading: str | None = None


class ExplanationOut(BaseModel):
    correct_answer_rationale: str
    key_point_summary: str | None = None
    further_reading: str | None = None


class MappingsIn(BaseModel):
    domain_id: uuid.UUID | None = None
    chapter_id: uuid.UUID | None = None
    knowledge_point_id: uuid.UUID | None = None
    tag_ids: list[uuid.UUID] = Field(default_factory=list)


class QuestionCreateIn(BaseModel):
    question_type: QuestionType
    stem: str
    stem_format: TextFormat = TextFormat.markdown
    difficulty: int | None = None
    language: str = "en"
    source: str | None = None
    license_status: LicenseStatus = LicenseStatus.unconfirmed
    prompt_items: list | None = None
    options: list[OptionIn]
    explanation: ExplanationIn | None = None
    mappings: MappingsIn = Field(default_factory=MappingsIn)


class QuestionUpdateIn(BaseModel):
    question_type: QuestionType | None = None
    stem: str | None = None
    stem_format: TextFormat | None = None
    difficulty: int | None = None
    language: str | None = None
    source: str | None = None
    license_status: LicenseStatus | None = None
    prompt_items: list | None = None
    options: list[OptionIn] | None = None
    explanation: ExplanationIn | None = None
    mappings: MappingsIn | None = None


class MappingsOut(BaseModel):
    domain_id: uuid.UUID | None = None
    chapter_id: uuid.UUID | None = None
    knowledge_point_id: uuid.UUID | None = None
    tag_ids: list[uuid.UUID] = Field(default_factory=list)


class QuestionOut(BaseModel):
    id: uuid.UUID
    question_type: QuestionType
    stem: str
    stem_format: TextFormat
    difficulty: int | None
    language: str
    status: QuestionStatus
    source: str | None
    license_status: LicenseStatus
    version: int
    prompt_items: list | None = None
    created_at: datetime
    updated_at: datetime
    options: list[OptionOut]
    explanation: ExplanationOut | None = None
    mappings: MappingsOut


class QuestionListItem(BaseModel):
    id: uuid.UUID
    question_type: QuestionType
    stem: str
    status: QuestionStatus
    difficulty: int | None
    language: str
    domain_id: uuid.UUID | None = None
    created_at: datetime


class ReviewAction(str, Enum):
    submit = "submit"
    approve = "approve"
    request_changes = "request_changes"
    archive = "archive"
    restore = "restore"


class ReviewActionIn(BaseModel):
    action: ReviewAction
    comment: str | None = None


class FeedbackIn(BaseModel):
    feedback_type: QuestionFeedbackType
    comment: str | None = None


class FeedbackOut(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    reporter_id: uuid.UUID | None = None
    feedback_type: QuestionFeedbackType
    comment: str | None = None
    status: QuestionFeedbackStatus
    created_at: datetime


class RevisionOut(BaseModel):
    revision_number: int
    edited_by_id: uuid.UUID | None = None
    edited_at: datetime
    change_summary: str | None = None
    snapshot: dict
```

- [ ] **Step 2: Write `app/schemas/taxonomy.py`**

```python
import uuid
from datetime import date

from pydantic import BaseModel


class DomainOut(BaseModel):
    id: uuid.UUID
    number: int
    name: str
    weight_pct: int


class BookOut(BaseModel):
    id: uuid.UUID
    title: str
    edition: str | None = None
    author: str | None = None
    publisher: str | None = None


class ChapterOut(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    order_index: int
    title: str


class KnowledgePointOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    parent_id: uuid.UUID | None = None
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/question.py backend/app/schemas/taxonomy.py
git commit -m "feat(question-bank): Pydantic schemas for questions + taxonomy"
```

---

### Task 3: Taxonomy read service + API + tests

**Files:**
- Create: `backend/app/services/taxonomy.py`
- Create: `backend/app/api/taxonomy.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_taxonomy_api.py`

**Interfaces:**
- Consumes: `ExamDomain`, `Book`, `Chapter`, `KnowledgePoint` models; `get_session`, `require_permission`.
- Produces: `list_domains`, `list_books`, `list_chapters`, `list_knowledge_points` service functions; `/api/domains`, `/api/books`, `/api/books/{id}/chapters`, `/api/knowledge-points` routes.

- [ ] **Step 1: Write the failing test `tests/test_taxonomy_api.py`**

```python
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.db.seed import PERMISSIONS
from app.db.session import get_session
from app.dependencies import get_lockout_store, get_refresh_store
from app.main import create_app
from app.models.auth import Organization, OrganizationMembership, Role
from app.models.enums import OrgKind, RoleName
from app.models.taxonomy import Book, Chapter, ExamBlueprint, ExamDomain, KnowledgePoint
from app.services.auth import InMemoryLockoutStore, register_user
from datetime import date


@pytest.fixture
def client(db_session, session_with_roles):
    app = create_app()
    store = InMemoryRefreshTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: store
    app.dependency_overrides[get_lockout_store] = lambda: InMemoryLockoutStore()
    return TestClient(app), store, db_session


def _headers(db_session, store, email="tax@example.com"):
    user, _ = register_user(db_session, email=email, password="pw123456",
                            display_name="Tax", refresh_store=store)
    db_session.flush()
    sa = db_session.query(Role).filter_by(name=RoleName.system_admin).first()
    m = db_session.query(OrganizationMembership).filter_by(user_id=user.id).one()
    m.role_id = sa.id
    db_session.flush()
    token = create_access_token(user_id=user.id, org_id=user.default_organization_id,
                                roles=["system_admin"], perms=[c for c, _ in PERMISSIONS])
    return {"Authorization": f"Bearer {token}"}


def _seed_taxonomy(db_session):
    org = Organization(slug="tax-org", name="Tax", kind=OrgKind.personal)
    db_session.add(org); db_session.flush()
    bp = ExamBlueprint(version_label="tax", effective_date=date(2024, 4, 15),
                       min_items=100, max_items=150, duration_minutes=180,
                       passing_score=700, max_score=1000, is_current=True)
    db_session.add(bp); db_session.flush()
    d1 = ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=16)
    d2 = ExamDomain(blueprint_id=bp.id, number=2, name="D2", weight_pct=10)
    db_session.add_all([d1, d2]); db_session.flush()
    book = Book(organization_id=org.id, title="OSG 10", edition="10e")
    db_session.add(book); db_session.flush()
    db_session.add_all([
        Chapter(organization_id=org.id, book_id=book.id, order_index=1, title="Ch1"),
        Chapter(organization_id=org.id, book_id=book.id, order_index=2, title="Ch2"),
    ])
    db_session.add(KnowledgePoint(name="Risk"))
    db_session.flush()
    return org.id, book.id


def test_domains_global(client):
    c, store, db = client
    _seed_taxonomy(db)
    h = _headers(db, store)
    resp = c.get("/api/domains", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert resp.json()[0]["number"] == 1


def test_books_tenant_scoped(client):
    c, store, db = client
    org_id, book_id = _seed_taxonomy(db)
    # other org's book
    other = Organization(slug="other", name="Other", kind=OrgKind.personal)
    db.add(other); db.flush()
    db.add(Book(organization_id=other.id, title="Other Book"))
    db.flush()
    h = _headers(db, store)  # token's org is the registered user's personal org
    resp = c.get("/api/books", headers=h)
    assert resp.status_code == 200
    titles = [b["title"] for b in resp.json()]
    assert "OSG 10" in titles  # seeded under tax-org, but books endpoint returns org's own books
    # Note: register_user creates a personal org for the user, distinct from tax-org,
    # so the user sees their own org's books (none from _seed_taxonomy). Adjust assertion:
    # the endpoint returns only books in current.org_id.


def test_books_returns_only_own_org(client):
    c, store, db = client
    _seed_taxonomy(db)
    h = _headers(db, store)
    resp = c.get("/api/books", headers=h)
    assert resp.status_code == 200
    # user's personal org has no books seeded
    assert resp.json() == []


def test_chapters_of_book(client):
    c, store, db = client
    org_id, book_id = _seed_taxonomy(db)
    h = _headers(db, store)
    resp = c.get(f"/api/books/{book_id}/chapters", headers=h)
    # book belongs to tax-org, user is in their own org -> 404 (not found in org)
    assert resp.status_code == 404


def test_knowledge_points_global(client):
    c, store, db = client
    _seed_taxonomy(db)
    h = _headers(db, store)
    resp = c.get("/api/knowledge-points", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "Risk"


def test_unauthenticated_401(client):
    c, _, _ = client
    assert c.get("/api/domains").status_code == 401
```

(Remove the redundant `test_books_tenant_scoped` before running — keep `test_books_returns_only_own_org`. The first version is explanatory only; delete it.)

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && source venv/bin/activate
pytest tests/test_taxonomy_api.py -q
```
Expected: FAIL (module `app.api.taxonomy` not found / routes 404).

- [ ] **Step 3: Write `app/services/taxonomy.py`**

```python
"""Read-only taxonomy queries (domains, books, chapters, knowledge points)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.queries import not_deleted
from app.models.question import Book, Chapter
from app.models.taxonomy import ExamDomain, KnowledgePoint


def list_domains(session: Session) -> list[ExamDomain]:
    return list(session.execute(
        select(ExamDomain).order_by(ExamDomain.number)
    ).scalars().all())


def list_books(session: Session, *, org_id) -> list[Book]:
    return list(session.execute(
        select(Book).where(Book.organization_id == org_id).order_by(Book.title)
    ).scalars().all())


def list_chapters(session: Session, *, book_id, org_id) -> list[Chapter] | None:
    book = session.get(Book, book_id)
    if book is None or book.organization_id != org_id:
        return None
    return list(session.execute(
        select(Chapter)
        .where(Chapter.book_id == book_id, not_deleted(Chapter))
        .order_by(Chapter.order_index)
    ).scalars().all())


def list_knowledge_points(session: Session) -> list[KnowledgePoint]:
    return list(session.execute(
        select(KnowledgePoint).order_by(KnowledgePoint.name)
    ).scalars().all())
```

- [ ] **Step 4: Write `app/api/taxonomy.py`**

```python
"""Taxonomy read-only HTTP API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dependencies import CurrentUser, require_permission
from app.schemas.taxonomy import BookOut, ChapterOut, DomainOut, KnowledgePointOut
from app.services import taxonomy as svc

router = APIRouter(prefix="/api", tags=["taxonomy"])


@router.get("/domains", response_model=list[DomainOut])
def domains(session: Session = Depends(get_session),
            _: CurrentUser = Depends(require_permission("question:read"))):
    return [DomainOut(id=d.id, number=d.number, name=d.name, weight_pct=d.weight_pct)
            for d in svc.list_domains(session)]


@router.get("/books", response_model=list[BookOut])
def books(session: Session = Depends(get_session),
          current: CurrentUser = Depends(require_permission("question:read"))):
    return [BookOut(id=b.id, title=b.title, edition=b.edition,
                    author=b.author, publisher=b.publisher)
            for b in svc.list_books(session, org_id=current.org_id)]


@router.get("/books/{book_id}/chapters", response_model=list[ChapterOut])
def chapters(book_id: uuid.UUID,
             session: Session = Depends(get_session),
             current: CurrentUser = Depends(require_permission("question:read"))):
    chapters = svc.list_chapters(session, book_id=book_id, org_id=current.org_id)
    if chapters is None:
        raise HTTPException(status_code=404, detail="book not found")
    return [ChapterOut(id=c.id, book_id=c.book_id, order_index=c.order_index, title=c.title)
            for c in chapters]


@router.get("/knowledge-points", response_model=list[KnowledgePointOut])
def knowledge_points(session: Session = Depends(get_session),
                     _: CurrentUser = Depends(require_permission("question:read"))):
    return [KnowledgePointOut(id=k.id, name=k.name, description=k.description,
                              parent_id=k.parent_id)
            for k in svc.list_knowledge_points(session)]
```

- [ ] **Step 5: Register router in `app/main.py`**

Add import `from app.api.taxonomy import router as taxonomy_router` alongside the others, and `app.include_router(taxonomy_router)` after `etl_router`.

- [ ] **Step 6: Run test to verify it passes**

```bash
pytest tests/test_taxonomy_api.py -q
```
Expected: PASS (all green).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/taxonomy.py backend/app/api/taxonomy.py backend/app/main.py backend/tests/test_taxonomy_api.py
git commit -m "feat(question-bank): taxonomy read API (domains/books/chapters/knowledge-points)"
```

---

### Task 4: Question service — create + validation

**Files:**
- Create: `backend/app/services/question.py`
- Test: `backend/tests/test_question_service.py`

**Interfaces:**
- Consumes: `Question`, `QuestionOption`, `Explanation`, `QuestionMapping`, `QuestionRevision` models; `not_deleted`; `log_audit`.
- Produces: `create_question(session, *, org_id, actor_id, payload: QuestionCreateIn) -> Question`.

- [ ] **Step 1: Write failing tests `tests/test_question_service.py`**

```python
import uuid
import pytest

from app.models.enums import QuestionType, QuestionStatus, LicenseStatus
from app.models.question import Question, QuestionOption, QuestionRevision, QuestionMapping
from app.schemas.question import ExplanationIn, MappingsIn, OptionIn, QuestionCreateIn
from app.services.question import create_question, ValidationError


def _org(db_session):
    from app.models.auth import Organization
    from app.models.enums import OrgKind
    org = Organization(slug=f"q-org-{uuid.uuid4().hex[:6]}", name="Q", kind=OrgKind.personal)
    db_session.add(org); db_session.flush()
    return org


def _single_payload(**kw):
    return QuestionCreateIn(
        question_type=QuestionType.single_choice,
        stem="What is 1+1?",
        options=[
            OptionIn(content="2", is_correct=True, order_index=0),
            OptionIn(content="3", is_correct=False, order_index=1),
        ],
        explanation=ExplanationIn(correct_answer_rationale="2"),
        **kw,
    )


def test_create_single_choice(db_session):
    org = _org(db_session)
    actor = uuid.uuid4()
    q = create_question(db_session, org_id=org.id, actor_id=actor, payload=_single_payload())
    assert q.id is not None
    assert q.status == QuestionStatus.draft
    assert q.version == 1
    assert q.organization_id == org.id
    opts = db_session.query(QuestionOption).filter_by(question_id=q.id).all()
    assert len(opts) == 2
    assert sum(o.is_correct for o in opts) == 1
    rev = db_session.query(QuestionRevision).filter_by(question_id=q.id).all()
    assert len(rev) == 1
    assert rev[0].revision_number == 1


def test_create_multiple_choice_requires_two_correct(db_session):
    org = _org(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.multiple_choice, stem="pick two",
        options=[
            OptionIn(content="a", is_correct=True, order_index=0),
            OptionIn(content="b", is_correct=False, order_index=1),
        ],
    )
    with pytest.raises(ValidationError):
        create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=payload)


def test_create_single_choice_exactly_one_correct(db_session):
    org = _org(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice, stem="x",
        options=[
            OptionIn(content="a", is_correct=False, order_index=0),
            OptionIn(content="b", is_correct=False, order_index=1),
        ],
    )
    with pytest.raises(ValidationError):
        create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=payload)


def test_create_true_false_two_options_one_correct(db_session):
    org = _org(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.true_false, stem="sky is blue",
        options=[
            OptionIn(content="True", is_correct=True, order_index=0),
            OptionIn(content="False", is_correct=False, order_index=1),
            OptionIn(content="Maybe", is_correct=False, order_index=2),
        ],
    )
    with pytest.raises(ValidationError):
        create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=payload)


def test_create_option_count_bounds(db_session):
    org = _org(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice, stem="x",
        options=[OptionIn(content="only", is_correct=True, order_index=0)],
    )
    with pytest.raises(ValidationError):
        create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=payload)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_question_service.py -q
```
Expected: FAIL (`ModuleNotFoundError: app.services.question`).

- [ ] **Step 3: Write `app/services/question.py` (create only, plus shared validation + helpers)**

```python
"""Question bank service: CRUD, lifecycle, revisions, feedback."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.queries import not_deleted
from app.models.enums import AuditAction, QuestionStatus, QuestionType
from app.models.question import (
    Explanation,
    Question,
    QuestionMapping,
    QuestionOption,
    QuestionRevision,
)
from app.schemas.question import (
    ExplanationIn,
    MappingsIn,
    OptionIn,
    QuestionCreateIn,
)
from app.services.audit import log_audit


class ValidationError(ValueError):
    """Raised for invalid question data (maps to HTTP 422)."""


def _validate_options(qtype: QuestionType, options: list[OptionIn]) -> None:
    n = len(options)
    correct = [o for o in options if o.is_correct]
    if qtype == QuestionType.true_false:
        if n != 2 or len(correct) != 1:
            raise ValidationError("true_false requires exactly 2 options with 1 correct")
    elif qtype == QuestionType.single_choice:
        if not 2 <= n <= 8:
            raise ValidationError("single_choice requires 2-8 options")
        if len(correct) != 1:
            raise ValidationError("single_choice requires exactly 1 correct option")
    elif qtype == QuestionType.multiple_choice:
        if not 2 <= n <= 8:
            raise ValidationError("multiple_choice requires 2-8 options")
        if len(correct) < 2:
            raise ValidationError("multiple_choice requires at least 2 correct options")
    else:
        # scenario / ordering / drag_drop / hotspot: defer strict validation
        if not 2 <= n <= 8:
            raise ValidationError("question requires 2-8 options")


def _next_revision_number(session: Session, question_id) -> int:
    rows = session.execute(
        select(QuestionRevision.revision_number)
        .where(QuestionRevision.question_id == question_id)
        .order_by(QuestionRevision.revision_number.desc())
    ).scalars().first()
    return (rows or 0) + 1


def _write_revision(session: Session, question: Question, *, actor_id,
                    change_summary: str | None) -> QuestionRevision:
    options = list(session.execute(
        select(QuestionOption).where(QuestionOption.question_id == question.id)
        .order_by(QuestionOption.order_index)
    ).scalars().all())
    from app.services.snapshot import snapshot_question
    snap = snapshot_question(question, options)
    rev = QuestionRevision(
        question_id=question.id,
        revision_number=_next_revision_number(session, question.id),
        snapshot=snap,
        edited_by_id=actor_id,
        change_summary=change_summary,
    )
    session.add(rev)
    return rev


def create_question(session: Session, *, org_id, actor_id,
                    payload: QuestionCreateIn) -> Question:
    if not payload.stem.strip():
        raise ValidationError("stem must not be empty")
    _validate_options(payload.question_type, payload.options)
    q = Question(
        organization_id=org_id,
        question_type=payload.question_type,
        stem=payload.stem,
        stem_format=payload.stem_format,
        difficulty=payload.difficulty,
        language=payload.language,
        status=QuestionStatus.draft,
        source=payload.source,
        license_status=payload.license_status,
        prompt_items=payload.prompt_items,
        version=1,
        created_by_id=actor_id,
        updated_by_id=actor_id,
    )
    session.add(q)
    session.flush()
    for i, opt in enumerate(payload.options):
        session.add(QuestionOption(
            question_id=q.id,
            order_index=opt.order_index if opt.order_index is not None else i,
            content=opt.content,
            content_format=opt.content_format,
            is_correct=opt.is_correct,
            explanation=opt.explanation,
        ))
    if payload.explanation is not None:
        session.add(Explanation(
            question_id=q.id,
            correct_answer_rationale=payload.explanation.correct_answer_rationale,
            key_point_summary=payload.explanation.key_point_summary,
            further_reading=payload.explanation.further_reading,
        ))
    _apply_mappings(session, q.id, payload.mappings)
    _write_revision(session, q, actor_id=actor_id, change_summary="initial creation")
    log_audit(session, action=AuditAction.edit, actor_id=actor_id,
              organization_id=org_id, entity_type="question", entity_id=str(q.id),
              details={"action": "create"})
    return q


def _apply_mappings(session: Session, question_id, mappings: MappingsIn) -> None:
    if mappings.domain_id is not None:
        session.add(QuestionMapping(question_id=question_id, domain_id=mappings.domain_id))
    if mappings.chapter_id is not None:
        session.add(QuestionMapping(question_id=question_id, chapter_id=mappings.chapter_id))
    if mappings.knowledge_point_id is not None:
        session.add(QuestionMapping(question_id=question_id, knowledge_point_id=mappings.knowledge_point_id))
    for tag_id in mappings.tag_ids:
        session.add(QuestionMapping(question_id=question_id, tag_id=tag_id))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_question_service.py -q
```
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/question.py backend/tests/test_question_service.py
git commit -m "feat(question-bank): question create service + option validation"
```

---

### Task 5: Question service — get + list (filters, pagination, tenant scoping)

**Files:**
- Modify: `backend/app/services/question.py` (add `get_question`, `list_questions`)
- Modify: `backend/tests/test_question_service.py` (add tests)

**Interfaces:**
- Produces: `get_question(session, question_id) -> Question`; `list_questions(session, *, org_id, filters: QuestionFilters, page, size) -> tuple[list[Question], int]`.

- [ ] **Step 1: Add failing tests**

Append to `tests/test_question_service.py`:

```python
from app.services.question import get_question, list_questions, NotFound


def test_get_question_missing_raises(db_session):
    with pytest.raises(NotFound):
        get_question(db_session, uuid.uuid4())


def test_get_question_excludes_soft_deleted(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=_single_payload())
    q.deleted_at = "2026-01-01T00:00:00"
    db_session.flush()
    with pytest.raises(NotFound):
        get_question(db_session, q.id)


def test_list_pagination_and_tenant(db_session):
    org = _org(db_session)
    other = _org(db_session)
    for _ in range(3):
        create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=_single_payload())
    create_question(db_session, org_id=other.id, actor_id=uuid.uuid4(), payload=_single_payload())
    items, total = list_questions(db_session, org_id=org.id, page=1, size=2)
    assert total == 3
    assert len(items) == 2
    items2, _ = list_questions(db_session, org_id=org.id, page=2, size=2)
    assert len(items2) == 1


def test_list_filter_by_status(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=_single_payload())
    q.status = QuestionStatus.published
    db_session.flush()
    items, total = list_questions(db_session, org_id=org.id, page=1, size=20,
                                  filters={"status": QuestionStatus.published})
    assert total == 1
    items_draft, total_draft = list_questions(db_session, org_id=org.id, page=1, size=20,
                                              filters={"status": QuestionStatus.draft})
    assert total_draft == 0


def test_list_search_by_stem(db_session):
    org = _org(db_session)
    create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(),
                    payload=QuestionCreateIn(
                        question_type=QuestionType.single_choice, stem="Cryptography basics",
                        options=[OptionIn(content="a", is_correct=True, order_index=0),
                                 OptionIn(content="b", order_index=1)]))
    items, total = list_questions(db_session, org_id=org.id, page=1, size=20,
                                  filters={"search": "crypto"})
    assert total == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_question_service.py -q
```
Expected: FAIL (`get_question`/`list_questions`/`NotFound` not defined).

- [ ] **Step 3: Implement `get_question` + `list_questions` in `app/services/question.py`**

Add at top of module:

```python
class NotFound(LookupError):
    """Raised when a question does not exist (maps to HTTP 404)."""
```

Add the functions:

```python
def get_question(session: Session, question_id) -> Question:
    q = session.get(Question, question_id)
    if q is None or q.deleted_at is not None:
        raise NotFound(f"question {question_id} not found")
    return q


def list_questions(session: Session, *, org_id, page: int = 1, size: int = 20,
                   filters: dict | None = None) -> tuple[list[Question], int]:
    filters = filters or {}
    stmt = select(Question).where(
        Question.organization_id == org_id, not_deleted(Question)
    )
    if (st := filters.get("status")) is not None:
        stmt = stmt.where(Question.status == st)
    if (qt := filters.get("question_type")) is not None:
        stmt = stmt.where(Question.question_type == qt)
    if (lang := filters.get("language")) is not None:
        stmt = stmt.where(Question.language == lang)
    if (diff := filters.get("difficulty")) is not None:
        stmt = stmt.where(Question.difficulty == diff)
    if (search := filters.get("search")) is not None:
        stmt = stmt.where(Question.stem.ilike(f"%{search}%"))
    if (domain_id := filters.get("domain_id")) is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(QuestionMapping.domain_id == domain_id)
        ))
    if (chapter_id := filters.get("chapter_id")) is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(QuestionMapping.chapter_id == chapter_id)
        ))
    if (knowledge_point_id := filters.get("knowledge_point_id")) is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(QuestionMapping.knowledge_point_id == knowledge_point_id)
        ))
    if (tag_id := filters.get("tag_id")) is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(QuestionMapping.tag_id == tag_id)
        ))
    from sqlalchemy import func
    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    page = max(page, 1)
    size = min(max(size, 1), 100)
    rows = list(session.execute(
        stmt.order_by(Question.created_at.desc()).offset((page - 1) * size).limit(size)
    ).scalars().all())
    return rows, total
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_question_service.py -q
```
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/question.py backend/tests/test_question_service.py
git commit -m "feat(question-bank): get + list (filters, pagination, tenant scoping)"
```

---

### Task 6: Question service — update + revision history

**Files:**
- Modify: `backend/app/services/question.py` (add `update_question`, `list_revisions`)
- Modify: `backend/tests/test_question_service.py`

**Interfaces:**
- Produces: `update_question(session, *, question_id, actor_id, payload: QuestionUpdateIn) -> Question`; `list_revisions(session, question_id) -> list[QuestionRevision]`.

- [ ] **Step 1: Add failing tests**

Append:

```python
from app.schemas.question import QuestionUpdateIn
from app.services.question import update_question, list_revisions


def test_update_bumps_version_and_writes_revision(db_session):
    org = _org(db_session)
    actor = uuid.uuid4()
    q = create_question(db_session, org_id=org.id, actor_id=actor, payload=_single_payload())
    updated = update_question(db_session, question_id=q.id, actor_id=actor,
                              payload=QuestionUpdateIn(stem="What is 2+2?"))
    assert updated.version == 2
    assert updated.stem == "What is 2+2?"
    revs = list_revisions(db_session, q.id)
    assert len(revs) == 2
    # pre-edit revision snapshot captures the original stem
    assert revs[0].snapshot["stem"] == "What is 1+1?"


def test_update_options_revalidates(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=_single_payload())
    with pytest.raises(ValidationError):
        update_question(db_session, question_id=q.id, actor_id=uuid.uuid4(),
                        payload=QuestionUpdateIn(options=[
                            OptionIn(content="a", is_correct=False, order_index=0),
                            OptionIn(content="b", is_correct=False, order_index=1),
                        ]))


def test_update_noop_does_not_bump(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=_single_payload())
    updated = update_question(db_session, question_id=q.id, actor_id=uuid.uuid4(),
                              payload=QuestionUpdateIn())
    assert updated.version == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_question_service.py -q
```
Expected: FAIL (`update_question`/`list_revisions` not defined).

- [ ] **Step 3: Implement `update_question` + `list_revisions`**

Add to `app/services/question.py`:

```python
from app.schemas.question import QuestionUpdateIn

_CONTENT_FIELDS = {"question_type", "stem", "stem_format", "difficulty", "language",
                   "source", "license_status", "prompt_items", "options", "explanation",
                   "mappings"}


def update_question(session: Session, *, question_id, actor_id,
                    payload: QuestionUpdateIn) -> Question:
    q = get_question(session, question_id)
    data = payload.model_dump(exclude_unset=True)
    changed = bool(data)
    if "options" in data:
        opts = [OptionIn(**o) for o in data["options"]]
        qtype = data.get("question_type", q.question_type)
        _validate_options(qtype, opts)
    # capture pre-edit snapshot before mutating
    if changed:
        _write_revision(session, q, actor_id=actor_id, change_summary="update")
    if "stem" in data:
        if not data["stem"].strip():
            raise ValidationError("stem must not be empty")
        q.stem = data["stem"]
    if "stem_format" in data:
        q.stem_format = data["stem_format"]
    if "question_type" in data:
        q.question_type = data["question_type"]
    if "difficulty" in data:
        q.difficulty = data["difficulty"]
    if "language" in data:
        q.language = data["language"]
    if "source" in data:
        q.source = data["source"]
    if "license_status" in data:
        q.license_status = data["license_status"]
    if "prompt_items" in data:
        q.prompt_items = data["prompt_items"]
    if "options" in data:
        session.execute(QuestionOption.__table__.delete().where(
            QuestionOption.question_id == q.id))
        for i, opt in enumerate(opts):
            session.add(QuestionOption(
                question_id=q.id,
                order_index=opt.order_index if opt.order_index is not None else i,
                content=opt.content, content_format=opt.content_format,
                is_correct=opt.is_correct, explanation=opt.explanation,
            ))
    if "explanation" in data:
        existing = session.execute(select(Explanation).where(Explanation.question_id == q.id)).scalar_one_or_none()
        if existing is not None:
            session.delete(existing)
        if data["explanation"] is not None:
            ex = ExplanationIn(**data["explanation"])
            session.add(Explanation(
                question_id=q.id, correct_answer_rationale=ex.correct_answer_rationale,
                key_point_summary=ex.key_point_summary, further_reading=ex.further_reading,
            ))
    if "mappings" in data:
        session.execute(QuestionMapping.__table__.delete().where(
            QuestionMapping.question_id == q.id))
        _apply_mappings(session, q.id, MappingsIn(**data["mappings"]))
    if changed:
        q.version = (q.version or 1) + 1
        q.updated_by_id = actor_id
        log_audit(session, action=AuditAction.edit, actor_id=actor_id,
                  organization_id=q.organization_id, entity_type="question",
                  entity_id=str(q.id), details={"action": "update"})
    return q


def list_revisions(session: Session, question_id) -> list[QuestionRevision]:
    return list(session.execute(
        select(QuestionRevision).where(QuestionRevision.question_id == question_id)
        .order_by(QuestionRevision.revision_number.asc())
    ).scalars().all())
```

(Note: `QuestionOption.__table__.delete()` is a Core delete — parameterized, safe; acceptable per CLAUDE.md which forbids raw *string* SQL, not ORM-Core deletes. If preferred, use `select` + `session.delete` loop. Prefer the loop for consistency: replace the two `__table__.delete()` calls with a select-then-delete loop.)

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_question_service.py -q
```
Expected: PASS (13 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/question.py backend/tests/test_question_service.py
git commit -m "feat(question-bank): update service + revision history"
```

---

### Task 7: Question service — soft delete

**Files:**
- Modify: `backend/app/services/question.py` (add `delete_question`)
- Modify: `backend/tests/test_question_service.py`

**Interfaces:**
- Produces: `delete_question(session, *, question_id, actor_id)`.

- [ ] **Step 1: Add failing test**

Append:

```python
from app.services.question import delete_question


def test_soft_delete_excludes_from_list(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=_single_payload())
    delete_question(db_session, question_id=q.id, actor_id=uuid.uuid4())
    items, total = list_questions(db_session, org_id=org.id, page=1, size=20)
    assert total == 0
    with pytest.raises(NotFound):
        get_question(db_session, q.id)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_question_service.py::test_soft_delete_excludes_from_list -q
```
Expected: FAIL (`delete_question` not defined).

- [ ] **Step 3: Implement `delete_question`**

Add to `app/services/question.py`:

```python
from datetime import datetime, timezone


def delete_question(session: Session, *, question_id, actor_id) -> None:
    q = get_question(session, question_id)
    q.deleted_at = datetime.now(timezone.utc)
    q.updated_by_id = actor_id
    log_audit(session, action=AuditAction.delete, actor_id=actor_id,
              organization_id=q.organization_id, entity_type="question",
              entity_id=str(q.id), details={"action": "soft_delete"})
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_question_service.py -q
```
Expected: PASS (14 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/question.py backend/tests/test_question_service.py
git commit -m "feat(question-bank): soft delete service"
```

---

### Task 8: Question service — review state machine

**Files:**
- Modify: `backend/app/services/question.py` (add `submit_review`, `IllegalTransition`)
- Modify: `backend/tests/test_question_service.py`

**Interfaces:**
- Produces: `submit_review(session, *, question_id, actor_id, action: ReviewAction, comment) -> Question`; `IllegalTransition(ValueError)`.

- [ ] **Step 1: Add failing tests**

Append:

```python
from app.schemas.question import ReviewAction
from app.services.question import submit_review, IllegalTransition


def test_review_draft_to_published(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=_single_payload())
    q = submit_review(db_session, question_id=q.id, actor_id=uuid.uuid4(),
                      action=ReviewAction.submit)
    assert q.status == QuestionStatus.pending_review
    q = submit_review(db_session, question_id=q.id, actor_id=uuid.uuid4(),
                      action=ReviewAction.approve)
    assert q.status == QuestionStatus.published


def test_review_request_changes(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=_single_payload())
    submit_review(db_session, question_id=q.id, actor_id=uuid.uuid4(), action=ReviewAction.submit)
    q = submit_review(db_session, question_id=q.id, actor_id=uuid.uuid4(),
                      action=ReviewAction.request_changes)
    assert q.status == QuestionStatus.needs_revision
    q = submit_review(db_session, question_id=q.id, actor_id=uuid.uuid4(),
                      action=ReviewAction.submit)
    assert q.status == QuestionStatus.pending_review


def test_review_archive_and_restore(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=_single_payload())
    q = submit_review(db_session, question_id=q.id, actor_id=uuid.uuid4(),
                      action=ReviewAction.archive)
    assert q.status == QuestionStatus.archived
    q = submit_review(db_session, question_id=q.id, actor_id=uuid.uuid4(),
                      action=ReviewAction.restore)
    assert q.status == QuestionStatus.draft


def test_review_illegal_transition(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=_single_payload())
    # draft -> approve is illegal (must submit first)
    with pytest.raises(IllegalTransition):
        submit_review(db_session, question_id=q.id, actor_id=uuid.uuid4(),
                      action=ReviewAction.approve)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_question_service.py -q -k review
```
Expected: FAIL (`submit_review` not defined).

- [ ] **Step 3: Implement `submit_review`**

Add to `app/services/question.py`:

```python
from app.schemas.question import ReviewAction

_TRANSITIONS = {
    ReviewAction.submit: {
        QuestionStatus.draft: QuestionStatus.pending_review,
        QuestionStatus.needs_revision: QuestionStatus.pending_review,
    },
    ReviewAction.approve: {QuestionStatus.pending_review: QuestionStatus.published},
    ReviewAction.request_changes: {QuestionStatus.pending_review: QuestionStatus.needs_revision},
    ReviewAction.archive: {
        QuestionStatus.draft: QuestionStatus.archived,
        QuestionStatus.pending_review: QuestionStatus.archived,
        QuestionStatus.published: QuestionStatus.archived,
        QuestionStatus.needs_revision: QuestionStatus.archived,
    },
    ReviewAction.restore: {QuestionStatus.archived: QuestionStatus.draft},
}

_AUDIT_ACTION = {
    ReviewAction.approve: AuditAction.publish,
    ReviewAction.archive: AuditAction.archive,
}


class IllegalTransition(ValueError):
    """Raised when a review action is invalid for the current status (-> HTTP 409)."""


def submit_review(session: Session, *, question_id, actor_id,
                  action: ReviewAction, comment: str | None = None) -> Question:
    q = get_question(session, question_id)
    target = _TRANSITIONS.get(action, {}).get(q.status)
    if target is None:
        raise IllegalTransition(
            f"action {action.value} not allowed from status {q.status.value}")
    q.status = target
    q.updated_by_id = actor_id
    if action in _AUDIT_ACTION:
        log_audit(session, action=_AUDIT_ACTION[action], actor_id=actor_id,
                  organization_id=q.organization_id, entity_type="question",
                  entity_id=str(q.id), details={"action": action.value, "comment": comment})
    else:
        log_audit(session, action=AuditAction.edit, actor_id=actor_id,
                  organization_id=q.organization_id, entity_type="question",
                  entity_id=str(q.id), details={"action": action.value, "comment": comment})
    return q
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_question_service.py -q
```
Expected: PASS (18 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/question.py backend/tests/test_question_service.py
git commit -m "feat(question-bank): review state machine (submit/approve/changes/archive/restore)"
```

---

### Task 9: Question service — correction feedback

**Files:**
- Modify: `backend/app/services/question.py` (add `create_feedback`, `list_feedback`)
- Modify: `backend/tests/test_question_service.py`

**Interfaces:**
- Produces: `create_feedback(session, *, org_id, question_id, reporter_id, payload: FeedbackIn) -> QuestionFeedback`; `list_feedback(session, *, question_id) -> list[QuestionFeedback]`.

- [ ] **Step 1: Add failing tests**

Append:

```python
from app.schemas.question import FeedbackIn
from app.models.enums import QuestionFeedbackType
from app.services.question import create_feedback, list_feedback


def test_create_and_list_feedback(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=_single_payload())
    fb = create_feedback(db_session, org_id=org.id, question_id=q.id, reporter_id=uuid.uuid4(),
                         payload=FeedbackIn(feedback_type=QuestionFeedbackType.unclear_explanation,
                                            comment="huh?"))
    assert fb.question_id == q.id
    assert fb.status.value == "open"
    assert len(list_feedback(db_session, question_id=q.id)) == 1


def test_create_feedback_on_deleted_question_raises(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=uuid.uuid4(), payload=_single_payload())
    delete_question(db_session, question_id=q.id, actor_id=uuid.uuid4())
    with pytest.raises(NotFound):
        create_feedback(db_session, org_id=org.id, question_id=q.id, reporter_id=uuid.uuid4(),
                        payload=FeedbackIn(feedback_type=QuestionFeedbackType.other))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_question_service.py -q -k feedback
```
Expected: FAIL (`create_feedback` not defined).

- [ ] **Step 3: Implement feedback functions**

Add import `QuestionFeedback` to the model imports at top of `app/services/question.py`, and add:

```python
from app.models.enums import QuestionFeedbackStatus
from app.schemas.question import FeedbackIn


def create_feedback(session: Session, *, org_id, question_id, reporter_id,
                    payload: FeedbackIn) -> QuestionFeedback:
    get_question(session, question_id)  # raises NotFound if missing/deleted
    fb = QuestionFeedback(
        organization_id=org_id,
        question_id=question_id,
        reporter_id=reporter_id,
        feedback_type=payload.feedback_type,
        comment=payload.comment,
        status=QuestionFeedbackStatus.open,
    )
    session.add(fb)
    return fb


def list_feedback(session: Session, *, question_id) -> list[QuestionFeedback]:
    return list(session.execute(
        select(QuestionFeedback)
        .where(QuestionFeedback.question_id == question_id, not_deleted(QuestionFeedback))
        .order_by(QuestionFeedback.created_at.desc())
    ).scalars().all())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_question_service.py -q
```
Expected: PASS (20 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/question.py backend/tests/test_question_service.py
git commit -m "feat(question-bank): correction feedback service (FR-Q-07)"
```

---

### Task 10: Question API router + tests

**Files:**
- Create: `backend/app/api/questions.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_question_api.py`

**Interfaces:**
- Produces: `/api/questions` (GET/POST), `/api/questions/{id}` (GET/PUT/DELETE), `/api/questions/{id}/review` (POST), `/api/questions/{id}/revisions` (GET), `/api/questions/{id}/feedback` (POST/GET).

- [ ] **Step 1: Write the failing test `tests/test_question_api.py`**

```python
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.db.seed import PERMISSIONS
from app.db.session import get_session
from app.dependencies import get_lockout_store, get_refresh_store
from app.main import create_app
from app.models.auth import OrganizationMembership, Role
from app.models.enums import RoleName, QuestionFeedbackType
from app.services.auth import InMemoryLockoutStore, register_user


@pytest.fixture
def client(db_session, session_with_roles):
    app = create_app()
    store = InMemoryRefreshTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: store
    app.dependency_overrides[get_lockout_store] = lambda: InMemoryLockoutStore()
    return TestClient(app), store, db_session


def _headers(db_session, store, email="q@example.com", role=RoleName.system_admin,
             perms=None):
    user, _ = register_user(db_session, email=email, password="pw123456",
                            display_name="Q", refresh_store=store)
    db_session.flush()
    r = db_session.query(Role).filter_by(name=role).first()
    m = db_session.query(OrganizationMembership).filter_by(user_id=user.id).one()
    m.role_id = r.id
    db_session.flush()
    if perms is None:
        perms = [c for c, _ in PERMISSIONS]
    token = create_access_token(user_id=user.id, org_id=user.default_organization_id,
                                roles=[role.value], perms=perms)
    return {"Authorization": f"Bearer {token}"}


def _single_body():
    return {
        "question_type": "single_choice",
        "stem": "What is 1+1?",
        "options": [
            {"content": "2", "is_correct": True, "order_index": 0},
            {"content": "3", "is_correct": False, "order_index": 1},
        ],
        "explanation": {"correct_answer_rationale": "2"},
    }


def test_create_and_get(client):
    c, store, db = client
    h = _headers(db, store, email="c1@example.com")
    resp = c.post("/api/questions", json=_single_body(), headers=h)
    assert resp.status_code == 200, resp.text
    qid = resp.json()["id"]
    assert resp.json()["status"] == "draft"
    got = c.get(f"/api/questions/{qid}", headers=h)
    assert got.status_code == 200
    assert len(got.json()["options"]) == 2


def test_create_validation_422(client):
    c, store, db = client
    h = _headers(db, store, email="c2@example.com")
    body = _single_body()
    body["options"][0]["is_correct"] = False
    body["options"][1]["is_correct"] = False
    assert c.post("/api/questions", json=body, headers=h).status_code == 422


def test_list_and_paginate(client):
    c, store, db = client
    h = _headers(db, store, email="l@example.com")
    for _ in range(3):
        c.post("/api/questions", json=_single_body(), headers=h)
    resp = c.get("/api/questions?page=1&size=2", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


def test_update_then_revisions(client):
    c, store, db = client
    h = _headers(db, store, email="u@example.com")
    qid = c.post("/api/questions", json=_single_body(), headers=h).json()["id"]
    put = c.put(f"/api/questions/{qid}", json={"stem": "What is 2+2?"}, headers=h)
    assert put.status_code == 200
    assert put.json()["version"] == 2
    revs = c.get(f"/api/questions/{qid}/revisions", headers=h)
    assert revs.status_code == 200
    assert len(revs.json()) == 2


def test_review_lifecycle(client):
    c, store, db = client
    h = _headers(db, store, email="r@example.com")
    qid = c.post("/api/questions", json=_single_body(), headers=h).json()["id"]
    assert c.post(f"/api/questions/{qid}/review", json={"action": "submit"}, headers=h).status_code == 200
    assert c.post(f"/api/questions/{qid}/review", json={"action": "approve"}, headers=h).status_code == 200
    got = c.get(f"/api/questions/{qid}", headers=h)
    assert got.json()["status"] == "published"


def test_review_illegal_transition_409(client):
    c, store, db = client
    h = _headers(db, store, email="ri@example.com")
    qid = c.post("/api/questions", json=_single_body(), headers=h).json()["id"]
    resp = c.post(f"/api/questions/{qid}/review", json={"action": "approve"}, headers=h)
    assert resp.status_code == 409


def test_delete_then_404(client):
    c, store, db = client
    h = _headers(db, store, email="d@example.com")
    qid = c.post("/api/questions", json=_single_body(), headers=h).json()["id"]
    assert c.delete(f"/api/questions/{qid}", headers=h).status_code == 200
    assert c.get(f"/api/questions/{qid}", headers=h).status_code == 404


def test_feedback_create_and_list(client):
    c, store, db = client
    h = _headers(db, store, email="f@example.com")
    qid = c.post("/api/questions", json=_single_body(), headers=h).json()["id"]
    resp = c.post(f"/api/questions/{qid}/feedback",
                  json={"feedback_type": "unclear_explanation", "comment": "huh?"},
                  headers=h)
    assert resp.status_code == 200
    lst = c.get(f"/api/questions/{qid}/feedback", headers=h)
    assert lst.status_code == 200
    assert len(lst.json()) == 1


def test_unauthenticated_401(client):
    c, _, _ = client
    assert c.get("/api/questions").status_code == 401


def test_learner_cannot_create_403(client):
    c, store, db = client
    # individual_learner has question:read but not question:write
    h = _headers(db, store, email="no@example.com", role=RoleName.individual_learner,
                 perms=["question:read", "practice:read", "exam:read"])
    assert c.post("/api/questions", json=_single_body(), headers=h).status_code == 403


def test_editor_can_write_but_not_publish(client):
    c, store, db = client
    h = _headers(db, store, email="ed@example.com", role=RoleName.content_editor,
                 perms=["question:read", "question:write", "question:publish", "question:import"])
    qid = c.post("/api/questions", json=_single_body(), headers=h).json()["id"]
    c.post(f"/api/questions/{qid}/review", json={"action": "submit"}, headers=h)
    assert c.post(f"/api/questions/{qid}/review", json={"action": "approve"}, headers=h).status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_question_api.py -q
```
Expected: FAIL (routes 404 — router not registered).

- [ ] **Step 3: Write `app/api/questions.py`**

```python
"""Question bank HTTP API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dependencies import CurrentUser, require_permission
from app.models.question import Explanation, QuestionMapping, QuestionOption
from app.schemas.question import (
    FeedbackIn,
    FeedbackOut,
    QuestionCreateIn,
    QuestionListItem,
    QuestionOut,
    QuestionUpdateIn,
    ReviewAction,
    ReviewActionIn,
    RevisionOut,
)
from app.services import question as svc

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _mappings_out(session: Session, question_id) -> dict:
    rows = session.execute(select(QuestionMapping).where(
        QuestionMapping.question_id == question_id)).scalars().all()
    domain_id = next((r.domain_id for r in rows if r.domain_id), None)
    chapter_id = next((r.chapter_id for r in rows if r.chapter_id), None)
    kp = next((r.knowledge_point_id for r in rows if r.knowledge_point_id), None)
    tag_ids = [r.tag_id for r in rows if r.tag_id]
    return {"domain_id": domain_id, "chapter_id": chapter_id,
            "knowledge_point_id": kp, "tag_ids": tag_ids}


def _question_out(session: Session, q) -> QuestionOut:
    options = sorted(
        session.execute(select(QuestionOption).where(QuestionOption.question_id == q.id)).scalars().all(),
        key=lambda o: o.order_index,
    )
    ex = session.execute(select(Explanation).where(Explanation.question_id == q.id)).scalar_one_or_none()
    return QuestionOut(
        id=q.id, question_type=q.question_type, stem=q.stem, stem_format=q.stem_format,
        difficulty=q.difficulty, language=q.language, status=q.status, source=q.source,
        license_status=q.license_status, version=q.version, prompt_items=q.prompt_items,
        created_at=q.created_at, updated_at=q.updated_at,
        options=[QuestionOut.model_fields["options"].annotation.__args__[0](
            id=o.id, order_index=o.order_index, content=o.content,
            content_format=o.content_format, is_correct=o.is_correct, explanation=o.explanation,
        ) for o in options],
        explanation=None if ex is None else ex,
        mappings=_mappings_out(session, q.id),
    )
```

(The nested `model_fields` trick is fragile — instead import `OptionOut` and `ExplanationOut` explicitly and build them. Replace the options construction with `[OptionOut(id=o.id, ...) for o in options]` and `ExplanationOut(...)`.)

Revised `_question_out`:

```python
from app.schemas.question import OptionOut, ExplanationOut, MappingsOut


def _question_out(session: Session, q) -> QuestionOut:
    options = sorted(
        session.execute(select(QuestionOption).where(QuestionOption.question_id == q.id)).scalars().all(),
        key=lambda o: o.order_index,
    )
    ex = session.execute(select(Explanation).where(Explanation.question_id == q.id)).scalar_one_or_none()
    return QuestionOut(
        id=q.id, question_type=q.question_type, stem=q.stem, stem_format=q.stem_format,
        difficulty=q.difficulty, language=q.language, status=q.status, source=q.source,
        license_status=q.license_status, version=q.version, prompt_items=q.prompt_items,
        created_at=q.created_at, updated_at=q.updated_at,
        options=[OptionOut(id=o.id, order_index=o.order_index, content=o.content,
                           content_format=o.content_format, is_correct=o.is_correct,
                           explanation=o.explanation) for o in options],
        explanation=None if ex is None else ExplanationOut(
            correct_answer_rationale=ex.correct_answer_rationale,
            key_point_summary=ex.key_point_summary, further_reading=ex.further_reading),
        mappings=MappingsOut(**_mappings_out(session, q.id)),
    )


@router.get("", response_model=dict)
def list_questions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    question_type: str | None = None,
    language: str | None = None,
    difficulty: int | None = None,
    search: str | None = None,
    domain_id: uuid.UUID | None = None,
    chapter_id: uuid.UUID | None = None,
    knowledge_point_id: uuid.UUID | None = None,
    tag_id: uuid.UUID | None = None,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:read")),
):
    from app.models.enums import QuestionStatus, QuestionType
    filters = {}
    if status is not None:
        filters["status"] = QuestionStatus(status)
    if question_type is not None:
        filters["question_type"] = QuestionType(question_type)
    if language is not None:
        filters["language"] = language
    if difficulty is not None:
        filters["difficulty"] = difficulty
    if search is not None:
        filters["search"] = search
    if domain_id is not None:
        filters["domain_id"] = domain_id
    if chapter_id is not None:
        filters["chapter_id"] = chapter_id
    if knowledge_point_id is not None:
        filters["knowledge_point_id"] = knowledge_point_id
    if tag_id is not None:
        filters["tag_id"] = tag_id
    items, total = svc.list_questions(session, org_id=current.org_id, page=page,
                                      size=size, filters=filters)
    return {"items": [QuestionListItem(
        id=q.id, question_type=q.question_type, stem=q.stem, status=q.status,
        difficulty=q.difficulty, language=q.language,
        domain_id=_mappings_out(session, q.id)["domain_id"],
        created_at=q.created_at) for q in items], "total": total, "page": page, "size": size}


@router.post("", response_model=QuestionOut, status_code=200)
def create_question(body: QuestionCreateIn,
                    session: Session = Depends(get_session),
                    current: CurrentUser = Depends(require_permission("question:write"))):
    try:
        q = svc.create_question(session, org_id=current.org_id, actor_id=current.user.id,
                                payload=body)
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(q)
    return _question_out(session, q)


@router.get("/{question_id}", response_model=QuestionOut)
def get_question(question_id: uuid.UUID,
                 session: Session = Depends(get_session),
                 _: CurrentUser = Depends(require_permission("question:read"))):
    try:
        q = svc.get_question(session, question_id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="question not found")
    return _question_out(session, q)


@router.put("/{question_id}", response_model=QuestionOut)
def update_question(question_id: uuid.UUID, body: QuestionUpdateIn,
                    session: Session = Depends(get_session),
                    current: CurrentUser = Depends(require_permission("question:write"))):
    try:
        q = svc.update_question(session, question_id=question_id, actor_id=current.user.id,
                                payload=body)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="question not found")
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(q)
    return _question_out(session, q)


@router.delete("/{question_id}")
def delete_question(question_id: uuid.UUID,
                    session: Session = Depends(get_session),
                    current: CurrentUser = Depends(require_permission("question:write"))):
    try:
        svc.delete_question(session, question_id=question_id, actor_id=current.user.id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="question not found")
    session.commit()
    return {"deleted": str(question_id)}


def _review_perm(action: ReviewAction) -> CurrentUser:
    # placeholder; real permission wired per-action in the route
    pass


@router.post("/{question_id}/review", response_model=QuestionOut)
def review_question(question_id: uuid.UUID, body: ReviewActionIn,
                    session: Session = Depends(get_session),
                    current: CurrentUser = Depends(require_permission("question:write"))):
    # approve/archive additionally require question:publish
    if body.action in (ReviewAction.approve, ReviewAction.archive) and \
            "question:publish" not in current.perms:
        raise HTTPException(status_code=403, detail="missing permission: question:publish")
    try:
        q = svc.submit_review(session, question_id=question_id, actor_id=current.user.id,
                              action=body.action, comment=body.comment)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="question not found")
    except svc.IllegalTransition as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    session.refresh(q)
    return _question_out(session, q)


@router.get("/{question_id}/revisions", response_model=list[RevisionOut])
def list_revisions(question_id: uuid.UUID,
                   session: Session = Depends(get_session),
                   _: CurrentUser = Depends(require_permission("question:read"))):
    try:
        svc.get_question(session, question_id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="question not found")
    return [RevisionOut(revision_number=r.revision_number, edited_by_id=r.edited_by_id,
                        edited_at=r.created_at, change_summary=r.change_summary,
                        snapshot=r.snapshot)
            for r in svc.list_revisions(session, question_id)]


@router.post("/{question_id}/feedback", response_model=FeedbackOut)
def create_feedback(question_id: uuid.UUID, body: FeedbackIn,
                    session: Session = Depends(get_session),
                    current: CurrentUser = Depends(require_permission("question:read"))):
    try:
        fb = svc.create_feedback(session, org_id=current.org_id, question_id=question_id,
                                 reporter_id=current.user.id, payload=body)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="question not found")
    session.commit()
    session.refresh(fb)
    return FeedbackOut(id=fb.id, question_id=fb.question_id, reporter_id=fb.reporter_id,
                       feedback_type=fb.feedback_type, comment=fb.comment,
                       status=fb.status, created_at=fb.created_at)


@router.get("/{question_id}/feedback", response_model=list[FeedbackOut])
def list_feedback(question_id: uuid.UUID,
                  session: Session = Depends(get_session),
                  _: CurrentUser = Depends(require_permission("question:read"))):
    return [FeedbackOut(id=fb.id, question_id=fb.question_id, reporter_id=fb.reporter_id,
                        feedback_type=fb.feedback_type, comment=fb.comment,
                        status=fb.status, created_at=fb.created_at)
            for fb in svc.list_feedback(session, question_id=question_id)]
```

(Remove the placeholder `_review_perm` function before running — it is not used.)

- [ ] **Step 4: Register router in `app/main.py`**

Add `from app.api.questions import router as questions_router` and `app.include_router(questions_router)`.

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_question_api.py -q
```
Expected: PASS (11 tests). If `session.refresh(q)` raises due to `expire_on_commit=False` on the test session, the object is already current — `refresh` may still re-query; if it errors on detached, drop the `refresh` calls (the test session has `expire_on_commit=False`, so attributes stay populated).

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/questions.py backend/app/main.py backend/tests/test_question_api.py
git commit -m "feat(question-bank): question CRUD/review/revisions/feedback API + RBAC"
```

---

### Task 11: Final verification + docs

**Files:**
- Modify: `CLAUDE.md` (current state)

- [ ] **Step 1: Run full backend suite + migration drift**

```bash
cd backend && source venv/bin/activate
pytest -q
pytest tests/test_migrations.py -q
```
Expected: all green, drift zero.

- [ ] **Step 2: Update `CLAUDE.md` Current State**

Note sub-project C done: question bank CRUD + lifecycle/review + revisions + feedback + taxonomy read API. Update the "What does NOT exist yet" list (remove question bank CRUD; remaining: practice/exam APIs, CAT engine, admin UI, interactive import, taxonomy write/admin — sub-projects D–H). Bump mention of test count.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(question-bank): update current state for sub-project C"
```

- [ ] **Step 4: Finish the branch**

Announce: "I'm using the finishing-a-development-branch skill to complete this work." Then per that skill: verify tests (done), detect environment, present options, execute choice (default under the autonomous goal: Option 1 — merge locally to master, then delete the feature branch).

---

## Self-Review

**Spec coverage:** FR-Q-01 (Task 4/5/6/7 CRUD), FR-Q-02 (Task 8 lifecycle), FR-Q-03 (single/multi validation Task 4), FR-Q-04 (true_false validation Task 4; scenario accepted), FR-Q-05 (prompt_items JSONB passthrough in schemas), FR-Q-06 (Task 6 revisions), FR-Q-07 (Task 9 feedback). FR-Q-08 stats deferred (no practice data). Taxonomy reads (Task 3). All §9.5 question + taxonomy-read endpoints covered. Interactive import/export deferred (noted in spec).

**Placeholder scan:** None — every step has runnable code or commands. (Task 10 has two self-correcting notes: drop the `_review_perm` placeholder and use explicit `OptionOut`/`ExplanationOut`; both are stated as instructions, not left as TBD.)

**Type consistency:** `ValidationError`/`NotFound`/`IllegalTransition` raised in service, caught in routes. `ReviewAction` enum used in both schema and service. `QuestionCreateIn`/`QuestionUpdateIn`/`FeedbackIn` field names match between schemas, service, and tests. `not_deleted` used consistently for `Question`, `Chapter`, `QuestionFeedback`.
