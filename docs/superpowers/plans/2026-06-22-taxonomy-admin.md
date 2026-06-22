# Taxonomy Admin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the taxonomy write/admin layer (blueprints, domains, books, chapters, knowledge-point tree, KP↔domain bindings, tags) — all gated by `admin:manage_taxonomy`, audit-logged.

**Architecture:** New service module `app/services/taxonomy_admin.py` owns all write logic/validation/audit. Routes extend `app/api/taxonomy.py` (already `/api`-prefixed). Schemas extend `app/schemas/taxonomy.py`. No migration — all tables exist.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Pydantic v2, PostgreSQL.

## Global Constraints

- Tests run against `cissp_test` DB (per-test SAVEPOINT rollback) — never the dev `cissp` DB.
- ORM/parameterized queries only — no raw string SQL.
- Taxonomy (ExamBlueprint/ExamDomain/KnowledgePoint/KnowledgePointDomain/Tag) is GLOBAL; Book/Chapter are tenant-scoped (`organization_id` from `current.org_id`).
- All admin write routes gated by `require_permission("admin:manage_taxonomy")`; reads stay `question:read`.
- Every create/update/delete/set-current audit-logged via `log_audit` (`AuditAction.config_change` for global taxonomy; `edit`/`delete` for book/chapter).
- Service raises `ValidationError`/`NotFound`/`ConflictError`; routes map to 422/404/409. Caller commits after success.
- FK constraints require real rows — never random UUIDs for org/actor (use `_actor` helper in service tests).
- The unstaged `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` edit is NOT mine — never stage it.

---

## File Structure

- **Create:** `backend/app/services/taxonomy_admin.py` — all write logic, exceptions, validation, audit.
- **Modify:** `backend/app/schemas/taxonomy.py` — add write schemas (BlueprintIn/Out, DomainIn, BookIn, ChapterIn, KnowledgePointIn, TagIn, BindingIn).
- **Modify:** `backend/app/api/taxonomy.py` — add admin-gated write routes + admin sub-paths.
- **Create:** `backend/tests/test_taxonomy_admin_service.py` — service-layer tests.
- **Create:** `backend/tests/test_taxonomy_admin_api.py` — HTTP tests.
- **Modify:** `backend/app/main.py` — bump version (optional), router already registered.

---

### Task 1: Schemas + service skeleton + exceptions

**Files:**
- Modify: `backend/app/schemas/taxonomy.py`
- Create: `backend/app/services/taxonomy_admin.py`

**Interfaces:**
- Produces: exceptions `ValidationError(ValueError)`, `NotFound(LookupError)`, `ConflictError(ValueError)` in `app.services.taxonomy_admin`; write schemas in `app.schemas.taxonomy`.

- [ ] **Step 1: Add write schemas to `backend/app/schemas/taxonomy.py`**

Append to the existing file (after `KnowledgePointOut`):

```python
class BlueprintIn(BaseModel):
    version_label: str
    effective_date: date
    min_items: int
    max_items: int
    duration_minutes: int
    passing_score: int
    max_score: int


class BlueprintUpdateIn(BaseModel):
    version_label: str | None = None
    effective_date: date | None = None
    min_items: int | None = None
    max_items: int | None = None
    duration_minutes: int | None = None
    passing_score: int | None = None
    max_score: int | None = None


class DomainOut(BaseModel):
    id: uuid.UUID
    blueprint_id: uuid.UUID
    number: int
    name: str
    weight_pct: int


class BlueprintOut(BaseModel):
    id: uuid.UUID
    version_label: str
    effective_date: date
    min_items: int
    max_items: int
    duration_minutes: int
    passing_score: int
    max_score: int
    is_current: bool
    domains: list[DomainOut] = []


class DomainIn(BaseModel):
    number: int
    name: str
    weight_pct: int


class BookIn(BaseModel):
    title: str
    edition: str | None = None
    author: str | None = None
    publisher: str | None = None
    source_url: str | None = None


class ChapterIn(BaseModel):
    order_index: int
    title: str


class KnowledgePointIn(BaseModel):
    name: str
    description: str | None = None
    parent_id: uuid.UUID | None = None


class TagIn(BaseModel):
    name: str
    description: str | None = None


class BindingIn(BaseModel):
    domain_id: uuid.UUID
```

Also add `from datetime import date` to the imports at the top of the file.

Note: `DomainOut` already exists in the file — **replace** the existing `DomainOut` definition with the new one (adds `blueprint_id`). The read `/api/domains` route constructs `DomainOut(id=, number=, name=, weight_pct=)` — `blueprint_id` has no default, so that route must be updated in Task 4 to pass `blueprint_id=d.blueprint_id`. Track this.

- [ ] **Step 2: Create service skeleton `backend/app/services/taxonomy_admin.py`**

```python
"""Taxonomy admin write operations (sub-project D).

All write logic, validation, and audit logging for the taxonomy subsystem.
Global taxonomy (blueprints/domains/knowledge-points/bindings/tags) is not
org-scoped; books/chapters are tenant-scoped. Every mutation is audit-logged.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import AuditAction
from app.models.question import Book, Chapter, QuestionMapping
from app.models.taxonomy import (
    ExamBlueprint,
    ExamDomain,
    KnowledgePoint,
    KnowledgePointDomain,
    Tag,
)
from app.schemas.taxonomy import (
    BlueprintIn,
    BlueprintUpdateIn,
    BindingIn,
    BookIn,
    ChapterIn,
    DomainIn,
    KnowledgePointIn,
    TagIn,
)
from app.services.audit import log_audit


class ValidationError(ValueError):
    """Invalid input (maps to HTTP 422)."""


class NotFound(LookupError):
    """Entity not found (maps to HTTP 404)."""


class ConflictError(ValueError):
    """Operation conflicts with existing data (maps to HTTP 409)."""
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/taxonomy.py backend/app/services/taxonomy_admin.py
git commit -m "feat(taxonomy-admin): schemas + service skeleton"
```

---

### Task 2: ExamBlueprint service (create, list, get, set-current, update, delete)

**Files:**
- Modify: `backend/app/services/taxonomy_admin.py`
- Test: `backend/tests/test_taxonomy_admin_service.py` (create)

**Interfaces:**
- Produces: `create_blueprint(session, *, actor_id, payload: BlueprintIn) -> ExamBlueprint`, `list_blueprints(session) -> list[ExamBlueprint]`, `get_blueprint(session, blueprint_id) -> ExamBlueprint`, `update_blueprint(session, *, blueprint_id, actor_id, payload: BlueprintUpdateIn) -> ExamBlueprint`, `set_current_blueprint(session, *, blueprint_id, actor_id) -> ExamBlueprint`, `delete_blueprint(session, *, blueprint_id, actor_id) -> None`.

- [ ] **Step 1: Write failing tests** in `backend/tests/test_taxonomy_admin_service.py`

```python
"""Service-layer tests for taxonomy admin (sub-project D)."""

import pytest

from app.models.auth import Organization, User
from app.models.enums import AuditAction
from app.models.taxonomy import ExamBlueprint, ExamDomain
from app.schemas.taxonomy import BlueprintIn, BlueprintUpdateIn, DomainIn
from app.services import taxonomy_admin as svc


def _org(db_session):
    org = Organization(name="T", kind="personal")
    db_session.add(org)
    db_session.flush()
    return org


def _actor(db_session, org):
    user = User(
        email="admin@example.com",
        password_hash="x",
        display_name="A",
        default_organization_id=org.id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _bp_payload(**kw):
    base = dict(
        version_label="2026-04-15",
        effective_date="2026-04-15",
        min_items=100,
        max_items=150,
        duration_minutes=180,
        passing_score=700,
        max_score=1000,
    )
    base.update(kw)
    return BlueprintIn(**base)


def test_create_blueprint_validates_bounds(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    with pytest.raises(svc.ValidationError):
        svc.create_blueprint(
            db_session, actor_id=actor.id,
            payload=_bp_payload(min_items=200, max_items=100),
        )


def test_create_blueprint(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    assert bp.id is not None
    assert bp.is_current is False
    assert bp.version_label == "2026-04-15"


def test_set_current_flips_others(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    a = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload(version_label="a"))
    b = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload(version_label="b"))
    svc.set_current_blueprint(db_session, blueprint_id=a.id, actor_id=actor.id)
    assert svc.get_blueprint(db_session, a.id).is_current is True
    assert svc.get_blueprint(db_session, b.id).is_current is False
    svc.set_current_blueprint(db_session, blueprint_id=b.id, actor_id=actor.id)
    assert svc.get_blueprint(db_session, a.id).is_current is False
    assert svc.get_blueprint(db_session, b.id).is_current is True


def test_update_blueprint_ignores_is_current(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    svc.set_current_blueprint(db_session, blueprint_id=bp.id, actor_id=actor.id)
    updated = svc.update_blueprint(
        db_session, blueprint_id=bp.id, actor_id=actor.id,
        payload=BlueprintUpdateIn(max_items=160),
    )
    assert updated.max_items == 160
    assert updated.is_current is True  # unchanged


def test_delete_current_blueprint_refused(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    svc.set_current_blueprint(db_session, blueprint_id=bp.id, actor_id=actor.id)
    with pytest.raises(svc.ConflictError):
        svc.delete_blueprint(db_session, blueprint_id=bp.id, actor_id=actor.id)


def test_delete_blueprint_with_mapped_questions_refused(db_session, session_with_roles):
    db = session_with_roles
    org = _org(db)
    actor = _actor(db, org)
    bp = svc.create_blueprint(db, actor_id=actor.id, payload=_bp_payload())
    from app.schemas.taxonomy import DomainIn
    domain = svc.create_domain(db, blueprint_id=bp.id, actor_id=actor.id,
                                payload=DomainIn(number=1, name="D1", weight_pct=10))
    # a question mapping referencing this domain
    from app.models.question import Question, QuestionMapping
    from app.models.enums import QuestionType
    q = Question(organization_id=org.id, question_type=QuestionType.single_choice,
                 stem="x", created_by_id=actor.id)
    db.add(q)
    db.flush()
    db.add(QuestionMapping(question_id=q.id, domain_id=domain.id))
    db.flush()
    with pytest.raises(svc.ConflictError):
        svc.delete_blueprint(db, blueprint_id=bp.id, actor_id=actor.id)
```

Note: `test_delete_blueprint_with_mapped_questions_refused` references `svc.create_domain` (Task 3) — leave this test for now; it will fail until Task 3. Run only the blueprint tests in Step 2.

- [ ] **Step 2: Run blueprint tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_taxonomy_admin_service.py -k "blueprint and not mapped_questions" -v`
Expected: FAIL (functions not defined).

- [ ] **Step 3: Implement blueprint functions** in `backend/app/services/taxonomy_admin.py` (append after the exceptions):

```python
def _validate_blueprint_fields(*, min_items, max_items, duration_minutes,
                               passing_score, max_score, version_label):
    if not version_label or not version_label.strip():
        raise ValidationError("version_label is required")
    if min_items <= 0 or max_items <= 0 or min_items > max_items:
        raise ValidationError("require 0 < min_items <= max_items")
    if duration_minutes <= 0:
        raise ValidationError("duration_minutes must be positive")
    if not (0 < passing_score < max_score):
        raise ValidationError("require 0 < passing_score < max_score")


def create_blueprint(session: Session, *, actor_id, payload: BlueprintIn) -> ExamBlueprint:
    _validate_blueprint_fields(
        min_items=payload.min_items, max_items=payload.max_items,
        duration_minutes=payload.duration_minutes,
        passing_score=payload.passing_score, max_score=payload.max_score,
        version_label=payload.version_label,
    )
    bp = ExamBlueprint(
        version_label=payload.version_label,
        effective_date=payload.effective_date,
        min_items=payload.min_items, max_items=payload.max_items,
        duration_minutes=payload.duration_minutes,
        passing_score=payload.passing_score, max_score=payload.max_score,
        is_current=False,
    )
    session.add(bp)
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="exam_blueprint", entity_id=str(bp.id),
              details={"op": "create", "version_label": bp.version_label})
    return bp


def list_blueprints(session: Session) -> list[ExamBlueprint]:
    return list(
        session.execute(
            select(ExamBlueprint).order_by(ExamBlueprint.effective_date.desc())
        ).scalars().all()
    )


def get_blueprint(session: Session, blueprint_id) -> ExamBlueprint:
    bp = session.get(ExamBlueprint, blueprint_id)
    if bp is None:
        raise NotFound("blueprint not found")
    return bp


def update_blueprint(session: Session, *, blueprint_id, actor_id,
                     payload: BlueprintUpdateIn) -> ExamBlueprint:
    bp = get_blueprint(session, blueprint_id)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return bp
    # is_current is never set via update
    data.pop("is_current", None)
    merged = dict(
        version_label=bp.version_label, effective_date=bp.effective_date,
        min_items=bp.min_items, max_items=bp.max_items,
        duration_minutes=bp.duration_minutes,
        passing_score=bp.passing_score, max_score=bp.max_score,
    )
    merged.update(data)
    _validate_blueprint_fields(
        min_items=merged["min_items"], max_items=merged["max_items"],
        duration_minutes=merged["duration_minutes"],
        passing_score=merged["passing_score"], max_score=merged["max_score"],
        version_label=merged["version_label"],
    )
    for k, v in data.items():
        setattr(bp, k, v)
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="exam_blueprint", entity_id=str(bp.id),
              details={"op": "update", "fields": list(data.keys())})
    return bp


def set_current_blueprint(session: Session, *, blueprint_id, actor_id) -> ExamBlueprint:
    bp = get_blueprint(session, blueprint_id)
    others = session.execute(
        select(ExamBlueprint).where(ExamBlueprint.is_current.is_(True))
    ).scalars().all()
    for o in others:
        o.is_current = False
    bp.is_current = True
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="exam_blueprint", entity_id=str(bp.id),
              details={"op": "set_current"})
    return bp


def _blueprint_has_mapped_questions(session: Session, blueprint_id) -> bool:
    domain_ids = select(ExamDomain.id).where(ExamDomain.blueprint_id == blueprint_id)
    exists = session.execute(
        select(QuestionMapping.question_id)
        .where(QuestionMapping.domain_id.in_(domain_ids))
        .limit(1)
    ).first()
    return exists is not None


def delete_blueprint(session: Session, *, blueprint_id, actor_id) -> None:
    bp = get_blueprint(session, blueprint_id)
    if bp.is_current:
        raise ConflictError("cannot delete the current blueprint")
    if _blueprint_has_mapped_questions(session, blueprint_id):
        raise ConflictError("blueprint has domains referenced by questions")
    session.delete(bp)
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="exam_blueprint", entity_id=str(blueprint_id),
              details={"op": "delete"})
```

- [ ] **Step 4: Run blueprint tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_taxonomy_admin_service.py -k "blueprint and not mapped_questions" -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy_admin.py backend/tests/test_taxonomy_admin_service.py
git commit -m "feat(taxonomy-admin): exam blueprint CRUD + set-current"
```

---

### Task 3: ExamDomain service (create, list, update, delete)

**Files:**
- Modify: `backend/app/services/taxonomy_admin.py`
- Test: `backend/tests/test_taxonomy_admin_service.py` (append)

**Interfaces:**
- Produces: `create_domain(session, *, blueprint_id, actor_id, payload: DomainIn) -> ExamDomain`, `list_domains_for_blueprint(session, blueprint_id) -> list[ExamDomain]`, `update_domain(session, *, blueprint_id, domain_id, actor_id, payload: DomainIn) -> ExamDomain`, `delete_domain(session, *, blueprint_id, domain_id, actor_id) -> None`.

- [ ] **Step 1: Write failing tests** (append to `test_taxonomy_admin_service.py`)

```python
def test_create_domain_validates_weight(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    with pytest.raises(svc.ValidationError):
        svc.create_domain(db_session, blueprint_id=bp.id, actor_id=actor.id,
                          payload=DomainIn(number=1, name="D1", weight_pct=200))


def test_create_domain(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    d = svc.create_domain(db_session, blueprint_id=bp.id, actor_id=actor.id,
                          payload=DomainIn(number=1, name="D1", weight_pct=12))
    assert d.blueprint_id == bp.id
    assert d.weight_pct == 12


def test_delete_domain_with_mapped_questions_refused(db_session, session_with_roles):
    db = session_with_roles
    org = _org(db)
    actor = _actor(db, org)
    bp = svc.create_blueprint(db, actor_id=actor.id, payload=_bp_payload())
    domain = svc.create_domain(db, blueprint_id=bp.id, actor_id=actor.id,
                               payload=DomainIn(number=1, name="D1", weight_pct=10))
    from app.models.question import Question, QuestionMapping
    from app.models.enums import QuestionType
    q = Question(organization_id=org.id, question_type=QuestionType.single_choice,
                 stem="x", created_by_id=actor.id)
    db.add(q); db.flush()
    db.add(QuestionMapping(question_id=q.id, domain_id=domain.id)); db.flush()
    with pytest.raises(svc.ConflictError):
        svc.delete_domain(db, blueprint_id=bp.id, domain_id=domain.id, actor_id=actor.id)
```

- [ ] **Step 2: Run domain tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_taxonomy_admin_service.py -k domain -v`
Expected: FAIL.

- [ ] **Step 3: Implement domain functions** (append to `taxonomy_admin.py`)

```python
def _validate_domain(*, number, name, weight_pct):
    if number < 1:
        raise ValidationError("domain number must be >= 1")
    if not name or not name.strip():
        raise ValidationError("domain name is required")
    if not (0 <= weight_pct <= 100):
        raise ValidationError("weight_pct must be 0..100")


def create_domain(session: Session, *, blueprint_id, actor_id, payload: DomainIn) -> ExamDomain:
    get_blueprint(session, blueprint_id)  # raises NotFound
    _validate_domain(number=payload.number, name=payload.name, weight_pct=payload.weight_pct)
    d = ExamDomain(blueprint_id=blueprint_id, number=payload.number,
                   name=payload.name, weight_pct=payload.weight_pct)
    session.add(d)
    try:
        session.flush()
    except Exception as e:  # unique violation
        session.rollback()
        raise ConflictError("domain number already exists in blueprint") from e
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="exam_domain", entity_id=str(d.id),
              details={"op": "create", "blueprint_id": str(blueprint_id)})
    return d
```

Wait — `session.rollback()` inside a SAVEPOINT-backed test session would roll back the whole test transaction. Replace the try/except with a pre-check instead. Use this corrected version:

```python
def create_domain(session: Session, *, blueprint_id, actor_id, payload: DomainIn) -> ExamDomain:
    get_blueprint(session, blueprint_id)  # raises NotFound
    _validate_domain(number=payload.number, name=payload.name, weight_pct=payload.weight_pct)
    dup = session.execute(
        select(ExamDomain).where(
            ExamDomain.blueprint_id == blueprint_id, ExamDomain.number == payload.number
        )
    ).first()
    if dup is not None:
        raise ConflictError("domain number already exists in blueprint")
    d = ExamDomain(blueprint_id=blueprint_id, number=payload.number,
                   name=payload.name, weight_pct=payload.weight_pct)
    session.add(d)
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="exam_domain", entity_id=str(d.id),
              details={"op": "create", "blueprint_id": str(blueprint_id)})
    return d


def list_domains_for_blueprint(session: Session, blueprint_id) -> list[ExamDomain]:
    get_blueprint(session, blueprint_id)
    return list(
        session.execute(
            select(ExamDomain)
            .where(ExamDomain.blueprint_id == blueprint_id)
            .order_by(ExamDomain.number)
        ).scalars().all()
    )


def _get_domain(session: Session, blueprint_id, domain_id) -> ExamDomain:
    d = session.execute(
        select(ExamDomain).where(
            ExamDomain.id == domain_id, ExamDomain.blueprint_id == blueprint_id
        )
    ).scalar_one_or_none()
    if d is None:
        raise NotFound("domain not found")
    return d


def update_domain(session: Session, *, blueprint_id, domain_id, actor_id,
                  payload: DomainIn) -> ExamDomain:
    d = _get_domain(session, blueprint_id, domain_id)
    _validate_domain(number=payload.number, name=payload.name, weight_pct=payload.weight_pct)
    if payload.number != d.number:
        dup = session.execute(
            select(ExamDomain).where(
                ExamDomain.blueprint_id == blueprint_id, ExamDomain.number == payload.number
            )
        ).first()
        if dup is not None:
            raise ConflictError("domain number already exists in blueprint")
    d.number = payload.number
    d.name = payload.name
    d.weight_pct = payload.weight_pct
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="exam_domain", entity_id=str(d.id),
              details={"op": "update"})
    return d


def _domain_has_mapped_questions(session: Session, domain_id) -> bool:
    exists = session.execute(
        select(QuestionMapping.question_id)
        .where(QuestionMapping.domain_id == domain_id)
        .limit(1)
    ).first()
    return exists is not None


def delete_domain(session: Session, *, blueprint_id, domain_id, actor_id) -> None:
    d = _get_domain(session, blueprint_id, domain_id)
    if _domain_has_mapped_questions(session, domain_id):
        raise ConflictError("domain is referenced by questions")
    session.delete(d)
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="exam_domain", entity_id=str(domain_id),
              details={"op": "delete"})
```

- [ ] **Step 4: Run domain tests + the previously-deferred blueprint-mapped-questions test**

Run: `cd backend && source venv/bin/activate && pytest tests/test_taxonomy_admin_service.py -v`
Expected: PASS (all tests so far).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy_admin.py backend/tests/test_taxonomy_admin_service.py
git commit -m "feat(taxonomy-admin): exam domain CRUD with delete guards"
```

---

### Task 4: Book + Chapter service (tenant-scoped)

**Files:**
- Modify: `backend/app/services/taxonomy_admin.py`
- Test: `backend/tests/test_taxonomy_admin_service.py` (append)

**Interfaces:**
- Produces: `create_book(session, *, org_id, actor_id, payload: BookIn) -> Book`, `get_book(session, *, book_id, org_id) -> Book`, `update_book(...)`, `delete_book(...)`, `create_chapter(session, *, book_id, org_id, actor_id, payload: ChapterIn) -> Chapter`, `update_chapter(...)`, `delete_chapter(...)`.

- [ ] **Step 1: Write failing tests** (append)

```python
from app.schemas.taxonomy import BookIn, ChapterIn


def test_create_book(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    book = svc.create_book(db_session, org_id=org.id, actor_id=actor.id,
                           payload=BookIn(title="OSG"))
    assert book.organization_id == org.id
    assert book.title == "OSG"


def test_create_book_empty_title(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    with pytest.raises(svc.ValidationError):
        svc.create_book(db_session, org_id=org.id, actor_id=actor.id,
                        payload=BookIn(title="  "))


def test_get_book_tenant_isolation(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    book = svc.create_book(db_session, org_id=org.id, actor_id=actor.id,
                           payload=BookIn(title="OSG"))
    other_org = Organization(name="O2", kind="personal")
    db_session.add(other_org); db_session.flush()
    with pytest.raises(svc.NotFound):
        svc.get_book(db_session, book_id=book.id, org_id=other_org.id)


def test_delete_book_with_chapters_questions_refused(db_session, session_with_roles):
    db = session_with_roles
    org = _org(db)
    actor = _actor(db, org)
    book = svc.create_book(db, org_id=org.id, actor_id=actor.id, payload=BookIn(title="B"))
    ch = svc.create_chapter(db, book_id=book.id, org_id=org.id, actor_id=actor.id,
                            payload=ChapterIn(order_index=0, title="C1"))
    from app.models.question import Question, QuestionMapping
    from app.models.enums import QuestionType
    q = Question(organization_id=org.id, question_type=QuestionType.single_choice,
                 stem="x", created_by_id=actor.id)
    db.add(q); db.flush()
    db.add(QuestionMapping(question_id=q.id, chapter_id=ch.id)); db.flush()
    with pytest.raises(svc.ConflictError):
        svc.delete_book(db, book_id=book.id, org_id=org.id, actor_id=actor.id)


def test_create_chapter(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    book = svc.create_book(db_session, org_id=org.id, actor_id=actor.id, payload=BookIn(title="B"))
    ch = svc.create_chapter(db_session, book_id=book.id, org_id=org.id, actor_id=actor.id,
                            payload=ChapterIn(order_index=1, title="C1"))
    assert ch.book_id == book.id
    assert ch.order_index == 1


def test_delete_chapter_with_questions_refused(db_session, session_with_roles):
    db = session_with_roles
    org = _org(db)
    actor = _actor(db, org)
    book = svc.create_book(db, org_id=org.id, actor_id=actor.id, payload=BookIn(title="B"))
    ch = svc.create_chapter(db, book_id=book.id, org_id=org.id, actor_id=actor.id,
                            payload=ChapterIn(order_index=0, title="C1"))
    from app.models.question import Question, QuestionMapping
    from app.models.enums import QuestionType
    q = Question(organization_id=org.id, question_type=QuestionType.single_choice,
                 stem="x", created_by_id=actor.id)
    db.add(q); db.flush()
    db.add(QuestionMapping(question_id=q.id, chapter_id=ch.id)); db.flush()
    with pytest.raises(svc.ConflictError):
        svc.delete_chapter(db, book_id=book.id, chapter_id=ch.id,
                           org_id=org.id, actor_id=actor.id)
```

- [ ] **Step 2: Run book/chapter tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_taxonomy_admin_service.py -k "book or chapter" -v`
Expected: FAIL.

- [ ] **Step 3: Implement book + chapter functions** (append to `taxonomy_admin.py`)

```python
def _chapter_has_mapped_questions(session: Session, chapter_id) -> bool:
    exists = session.execute(
        select(QuestionMapping.question_id)
        .where(QuestionMapping.chapter_id == chapter_id)
        .limit(1)
    ).first()
    return exists is not None


def create_book(session: Session, *, org_id, actor_id, payload: BookIn) -> Book:
    if not payload.title or not payload.title.strip():
        raise ValidationError("book title is required")
    book = Book(organization_id=org_id, title=payload.title, edition=payload.edition,
                author=payload.author, publisher=payload.publisher, source_url=payload.source_url)
    session.add(book)
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              organization_id=org_id, entity_type="book", entity_id=str(book.id),
              details={"op": "create"})
    return book


def get_book(session: Session, *, book_id, org_id) -> Book:
    book = session.get(Book, book_id)
    if book is None or book.organization_id != org_id:
        raise NotFound("book not found")
    return book


def update_book(session: Session, *, book_id, org_id, actor_id, payload: BookIn) -> Book:
    book = get_book(session, book_id=book_id, org_id=org_id)
    if not payload.title or not payload.title.strip():
        raise ValidationError("book title is required")
    book.title = payload.title
    book.edition = payload.edition
    book.author = payload.author
    book.publisher = payload.publisher
    book.source_url = payload.source_url
    session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=actor_id, organization_id=org_id,
              entity_type="book", entity_id=str(book.id), details={"op": "update"})
    return book


def delete_book(session: Session, *, book_id, org_id, actor_id) -> None:
    book = get_book(session, book_id=book_id, org_id=org_id)
    # any chapter of this book mapped to questions?
    chapter_ids = select(Chapter.id).where(Chapter.book_id == book_id)
    blocked = session.execute(
        select(QuestionMapping.question_id)
        .where(QuestionMapping.chapter_id.in_(chapter_ids))
        .limit(1)
    ).first()
    if blocked is not None:
        raise ConflictError("book has chapters referenced by questions")
    session.delete(book)
    session.flush()
    log_audit(session, action=AuditAction.delete, actor_id=actor_id, organization_id=org_id,
              entity_type="book", entity_id=str(book_id), details={"op": "delete"})


def create_chapter(session: Session, *, book_id, org_id, actor_id, payload: ChapterIn) -> Chapter:
    book = get_book(session, book_id=book_id, org_id=org_id)
    if payload.order_index < 0:
        raise ValidationError("order_index must be >= 0")
    if not payload.title or not payload.title.strip():
        raise ValidationError("chapter title is required")
    ch = Chapter(organization_id=org_id, book_id=book.id, order_index=payload.order_index,
                 title=payload.title)
    session.add(ch)
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id, organization_id=org_id,
              entity_type="chapter", entity_id=str(ch.id), details={"op": "create"})
    return ch


def _get_chapter(session: Session, *, book_id, chapter_id, org_id) -> Chapter:
    ch = session.execute(
        select(Chapter).where(
            Chapter.id == chapter_id, Chapter.book_id == book_id,
            Chapter.organization_id == org_id,
        )
    ).scalar_one_or_none()
    if ch is None:
        raise NotFound("chapter not found")
    return ch


def update_chapter(session: Session, *, book_id, chapter_id, org_id, actor_id,
                   payload: ChapterIn) -> Chapter:
    ch = _get_chapter(session, book_id=book_id, chapter_id=chapter_id, org_id=org_id)
    if payload.order_index < 0:
        raise ValidationError("order_index must be >= 0")
    if not payload.title or not payload.title.strip():
        raise ValidationError("chapter title is required")
    ch.order_index = payload.order_index
    ch.title = payload.title
    session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=actor_id, organization_id=org_id,
              entity_type="chapter", entity_id=str(ch.id), details={"op": "update"})
    return ch


def delete_chapter(session: Session, *, book_id, chapter_id, org_id, actor_id) -> None:
    ch = _get_chapter(session, book_id=book_id, chapter_id=chapter_id, org_id=org_id)
    if _chapter_has_mapped_questions(session, chapter_id):
        raise ConflictError("chapter is referenced by questions")
    session.delete(ch)
    session.flush()
    log_audit(session, action=AuditAction.delete, actor_id=actor_id, organization_id=org_id,
              entity_type="chapter", entity_id=str(chapter_id), details={"op": "delete"})
```

- [ ] **Step 4: Run book/chapter tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_taxonomy_admin_service.py -k "book or chapter" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy_admin.py backend/tests/test_taxonomy_admin_service.py
git commit -m "feat(taxonomy-admin): book + chapter CRUD (tenant-scoped)"
```

---

### Task 5: KnowledgePoint tree service (create, get, update, delete with cycle prevention)

**Files:**
- Modify: `backend/app/services/taxonomy_admin.py`
- Test: `backend/tests/test_taxonomy_admin_service.py` (append)

**Interfaces:**
- Produces: `create_knowledge_point(session, *, actor_id, payload: KnowledgePointIn) -> KnowledgePoint`, `get_knowledge_point(session, kp_id) -> KnowledgePoint`, `update_knowledge_point(...)`, `delete_knowledge_point(...)`.

- [ ] **Step 1: Write failing tests** (append)

```python
from app.schemas.taxonomy import KnowledgePointIn


def test_create_kp(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    kp = svc.create_knowledge_point(db_session, actor_id=actor.id,
                                     payload=KnowledgePointIn(name="KP1"))
    assert kp.name == "KP1"
    assert kp.parent_id is None


def test_create_kp_cycle_self(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    kp = svc.create_knowledge_point(db_session, actor_id=actor.id,
                                     payload=KnowledgePointIn(name="KP1"))
    with pytest.raises(svc.ValidationError):
        svc.update_knowledge_point(
            db_session, kp_id=kp.id, actor_id=actor.id,
            payload=KnowledgePointIn(name="KP1", parent_id=kp.id),
        )


def test_create_kp_cycle_descendant(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    root = svc.create_knowledge_point(db_session, actor_id=actor.id,
                                       payload=KnowledgePointIn(name="root"))
    child = svc.create_knowledge_point(
        db_session, actor_id=actor.id,
        payload=KnowledgePointIn(name="child", parent_id=root.id),
    )
    # setting root's parent to child would create a cycle
    with pytest.raises(svc.ValidationError):
        svc.update_knowledge_point(
            db_session, kp_id=root.id, actor_id=actor.id,
            payload=KnowledgePointIn(name="root", parent_id=child.id),
        )


def test_delete_kp_with_children_refused(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    root = svc.create_knowledge_point(db_session, actor_id=actor.id,
                                       payload=KnowledgePointIn(name="root"))
    svc.create_knowledge_point(db_session, actor_id=actor.id,
                               payload=KnowledgePointIn(name="child", parent_id=root.id))
    with pytest.raises(svc.ConflictError):
        svc.delete_knowledge_point(db_session, kp_id=root.id, actor_id=actor.id)
```

- [ ] **Step 2: Run KP tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_taxonomy_admin_service.py -k "kp" -v`
Expected: FAIL.

- [ ] **Step 3: Implement KP functions** (append to `taxonomy_admin.py`)

```python
def _validate_kp(*, name):
    if not name or not name.strip():
        raise ValidationError("knowledge point name is required")


def _would_cycle(session: Session, kp_id, proposed_parent_id) -> bool:
    """True if setting kp_id's parent to proposed_parent_id creates a cycle.

    Walk up from proposed_parent; if we hit kp_id, it's a cycle.
    """
    if proposed_parent_id is None:
        return False
    cursor = proposed_parent_id
    seen = set()
    while cursor is not None and cursor not in seen:
        if cursor == kp_id:
            return True
        seen.add(cursor)
        row = session.execute(
            select(KnowledgePoint.parent_id).where(KnowledgePoint.id == cursor)
        ).first()
        if row is None:
            return False
        cursor = row[0]
    return False


def create_knowledge_point(session: Session, *, actor_id,
                           payload: KnowledgePointIn) -> KnowledgePoint:
    _validate_kp(name=payload.name)
    if payload.parent_id is not None:
        parent = session.get(KnowledgePoint, payload.parent_id)
        if parent is None:
            raise NotFound("parent knowledge point not found")
    kp = KnowledgePoint(name=payload.name, description=payload.description,
                        parent_id=payload.parent_id)
    session.add(kp)
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="knowledge_point", entity_id=str(kp.id),
              details={"op": "create"})
    return kp


def get_knowledge_point(session: Session, kp_id) -> KnowledgePoint:
    kp = session.get(KnowledgePoint, kp_id)
    if kp is None:
        raise NotFound("knowledge point not found")
    return kp


def update_knowledge_point(session: Session, *, kp_id, actor_id,
                           payload: KnowledgePointIn) -> KnowledgePoint:
    kp = get_knowledge_point(session, kp_id)
    _validate_kp(name=payload.name)
    if payload.parent_id is not None:
        if payload.parent_id == kp_id:
            raise ValidationError("knowledge point cannot be its own parent")
        parent = session.get(KnowledgePoint, payload.parent_id)
        if parent is None:
            raise NotFound("parent knowledge point not found")
        if _would_cycle(session, kp_id, payload.parent_id):
            raise ValidationError("setting this parent would create a cycle")
    kp.name = payload.name
    kp.description = payload.description
    kp.parent_id = payload.parent_id
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="knowledge_point", entity_id=str(kp.id),
              details={"op": "update"})
    return kp


def _kp_has_children(session: Session, kp_id) -> bool:
    exists = session.execute(
        select(KnowledgePoint.id).where(KnowledgePoint.parent_id == kp_id).limit(1)
    ).first()
    return exists is not None


def _kp_has_bindings(session: Session, kp_id) -> bool:
    exists = session.execute(
        select(KnowledgePointDomain.domain_id)
        .where(KnowledgePointDomain.knowledge_point_id == kp_id).limit(1)
    ).first()
    return exists is not None


def _kp_has_mapped_questions(session: Session, kp_id) -> bool:
    exists = session.execute(
        select(QuestionMapping.question_id)
        .where(QuestionMapping.knowledge_point_id == kp_id).limit(1)
    ).first()
    return exists is not None


def delete_knowledge_point(session: Session, *, kp_id, actor_id) -> None:
    kp = get_knowledge_point(session, kp_id)
    if _kp_has_children(session, kp_id):
        raise ConflictError("knowledge point has children")
    if _kp_has_bindings(session, kp_id):
        raise ConflictError("knowledge point has domain bindings")
    if _kp_has_mapped_questions(session, kp_id):
        raise ConflictError("knowledge point is referenced by questions")
    session.delete(kp)
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="knowledge_point", entity_id=str(kp_id),
              details={"op": "delete"})
```

- [ ] **Step 4: Run KP tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_taxonomy_admin_service.py -k "kp" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy_admin.py backend/tests/test_taxonomy_admin_service.py
git commit -m "feat(taxonomy-admin): knowledge-point tree with cycle prevention"
```

---

### Task 6: KP↔Domain binding + Tag service

**Files:**
- Modify: `backend/app/services/taxonomy_admin.py`
- Test: `backend/tests/test_taxonomy_admin_service.py` (append)

**Interfaces:**
- Produces: `bind_kp_domain(session, *, kp_id, actor_id, payload: BindingIn) -> KnowledgePointDomain`, `list_kp_domains(session, kp_id) -> list[ExamDomain]`, `unbind_kp_domain(session, *, kp_id, domain_id, actor_id) -> None`, `create_tag(...)`, `get_tag(...)`, `update_tag(...)`, `delete_tag(...)`, `list_tags(...)`.

- [ ] **Step 1: Write failing tests** (append)

```python
from app.schemas.taxonomy import BindingIn, TagIn


def test_bind_kp_domain(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    domain = svc.create_domain(db_session, blueprint_id=bp.id, actor_id=actor.id,
                               payload=DomainIn(number=1, name="D1", weight_pct=10))
    kp = svc.create_knowledge_point(db_session, actor_id=actor.id, payload=KnowledgePointIn(name="KP"))
    binding = svc.bind_kp_domain(db_session, kp_id=kp.id, actor_id=actor.id,
                                 payload=BindingIn(domain_id=domain.id))
    assert binding.knowledge_point_id == kp.id
    assert binding.domain_id == domain.id
    domains = svc.list_kp_domains(db_session, kp_id=kp.id)
    assert len(domains) == 1
    assert domains[0].id == domain.id


def test_bind_kp_domain_duplicate_refused(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    domain = svc.create_domain(db_session, blueprint_id=bp.id, actor_id=actor.id,
                               payload=DomainIn(number=1, name="D1", weight_pct=10))
    kp = svc.create_knowledge_point(db_session, actor_id=actor.id, payload=KnowledgePointIn(name="KP"))
    svc.bind_kp_domain(db_session, kp_id=kp.id, actor_id=actor.id,
                       payload=BindingIn(domain_id=domain.id))
    with pytest.raises(svc.ConflictError):
        svc.bind_kp_domain(db_session, kp_id=kp.id, actor_id=actor.id,
                           payload=BindingIn(domain_id=domain.id))


def test_unbind_kp_domain(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    domain = svc.create_domain(db_session, blueprint_id=bp.id, actor_id=actor.id,
                               payload=DomainIn(number=1, name="D1", weight_pct=10))
    kp = svc.create_knowledge_point(db_session, actor_id=actor.id, payload=KnowledgePointIn(name="KP"))
    svc.bind_kp_domain(db_session, kp_id=kp.id, actor_id=actor.id,
                       payload=BindingIn(domain_id=domain.id))
    svc.unbind_kp_domain(db_session, kp_id=kp.id, domain_id=domain.id, actor_id=actor.id)
    assert len(svc.list_kp_domains(db_session, kp_id=kp.id)) == 0


def test_create_tag(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    tag = svc.create_tag(db_session, actor_id=actor.id, payload=TagIn(name="crypto"))
    assert tag.name == "crypto"


def test_create_tag_duplicate_refused(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    svc.create_tag(db_session, actor_id=actor.id, payload=TagIn(name="crypto"))
    with pytest.raises(svc.ConflictError):
        svc.create_tag(db_session, actor_id=actor.id, payload=TagIn(name="crypto"))


def test_delete_tag_with_questions_refused(db_session, session_with_roles):
    db = session_with_roles
    org = _org(db)
    actor = _actor(db, org)
    tag = svc.create_tag(db, actor_id=actor.id, payload=TagIn(name="crypto"))
    from app.models.question import Question, QuestionMapping
    from app.models.enums import QuestionType
    q = Question(organization_id=org.id, question_type=QuestionType.single_choice,
                 stem="x", created_by_id=actor.id)
    db.add(q); db.flush()
    db.add(QuestionMapping(question_id=q.id, tag_id=tag.id)); db.flush()
    with pytest.raises(svc.ConflictError):
        svc.delete_tag(db, tag_id=tag.id, actor_id=actor.id)
```

- [ ] **Step 2: Run binding/tag tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_taxonomy_admin_service.py -k "bind or tag" -v`
Expected: FAIL.

- [ ] **Step 3: Implement binding + tag functions** (append to `taxonomy_admin.py`)

```python
def bind_kp_domain(session: Session, *, kp_id, actor_id,
                   payload: BindingIn) -> KnowledgePointDomain:
    get_knowledge_point(session, kp_id)
    domain = session.get(ExamDomain, payload.domain_id)
    if domain is None:
        raise NotFound("domain not found")
    dup = session.execute(
        select(KnowledgePointDomain).where(
            KnowledgePointDomain.knowledge_point_id == kp_id,
            KnowledgePointDomain.domain_id == payload.domain_id,
        )
    ).first()
    if dup is not None:
        raise ConflictError("knowledge point already bound to this domain")
    binding = KnowledgePointDomain(knowledge_point_id=kp_id, domain_id=payload.domain_id)
    session.add(binding)
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="knowledge_point_domain", entity_id=str(binding.id),
              details={"op": "create", "kp_id": str(kp_id), "domain_id": str(payload.domain_id)})
    return binding


def list_kp_domains(session: Session, kp_id) -> list[ExamDomain]:
    get_knowledge_point(session, kp_id)
    domain_ids = select(KnowledgePointDomain.domain_id).where(
        KnowledgePointDomain.knowledge_point_id == kp_id
    )
    return list(
        session.execute(
            select(ExamDomain).where(ExamDomain.id.in_(domain_ids)).order_by(ExamDomain.number)
        ).scalars().all()
    )


def unbind_kp_domain(session: Session, *, kp_id, domain_id, actor_id) -> None:
    get_knowledge_point(session, kp_id)
    binding = session.execute(
        select(KnowledgePointDomain).where(
            KnowledgePointDomain.knowledge_point_id == kp_id,
            KnowledgePointDomain.domain_id == domain_id,
        )
    ).scalar_one_or_none()
    if binding is None:
        raise NotFound("binding not found")
    session.delete(binding)
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="knowledge_point_domain", entity_id=str(binding.id),
              details={"op": "delete", "kp_id": str(kp_id), "domain_id": str(domain_id)})


def _validate_tag(*, name):
    if not name or not name.strip():
        raise ValidationError("tag name is required")


def create_tag(session: Session, *, actor_id, payload: TagIn) -> Tag:
    _validate_tag(name=payload.name)
    dup = session.execute(select(Tag).where(Tag.name == payload.name)).first()
    if dup is not None:
        raise ConflictError("tag name already exists")
    tag = Tag(name=payload.name, description=payload.description)
    session.add(tag)
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="tag", entity_id=str(tag.id), details={"op": "create"})
    return tag


def list_tags(session: Session) -> list[Tag]:
    return list(
        session.execute(select(Tag).order_by(Tag.name)).scalars().all()
    )


def get_tag(session: Session, tag_id) -> Tag:
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise NotFound("tag not found")
    return tag


def update_tag(session: Session, *, tag_id, actor_id, payload: TagIn) -> Tag:
    tag = get_tag(session, tag_id)
    _validate_tag(name=payload.name)
    if payload.name != tag.name:
        dup = session.execute(select(Tag).where(Tag.name == payload.name)).first()
        if dup is not None:
            raise ConflictError("tag name already exists")
    tag.name = payload.name
    tag.description = payload.description
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="tag", entity_id=str(tag.id), details={"op": "update"})
    return tag


def _tag_has_mapped_questions(session: Session, tag_id) -> bool:
    exists = session.execute(
        select(QuestionMapping.question_id)
        .where(QuestionMapping.tag_id == tag_id).limit(1)
    ).first()
    return exists is not None


def delete_tag(session: Session, *, tag_id, actor_id) -> None:
    tag = get_tag(session, tag_id)
    if _tag_has_mapped_questions(session, tag_id):
        raise ConflictError("tag is referenced by questions")
    session.delete(tag)
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=actor_id,
              entity_type="tag", entity_id=str(tag_id), details={"op": "delete"})
```

- [ ] **Step 4: Run binding/tag tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_taxonomy_admin_service.py -v`
Expected: PASS (full service test suite).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy_admin.py backend/tests/test_taxonomy_admin_service.py
git commit -m "feat(taxonomy-admin): KP-domain bindings + tag CRUD"
```

---

### Task 7: HTTP API — blueprints + domains admin routes

**Files:**
- Modify: `backend/app/api/taxonomy.py`
- Modify: `backend/app/schemas/taxonomy.py` (fix `DomainOut` usage in read route)
- Test: `backend/tests/test_taxonomy_admin_api.py` (create)

**Interfaces:**
- Produces: routes `POST/GET /api/admin/blueprints`, `GET/PUT/DELETE /api/admin/blueprints/{id}`, `POST /api/admin/blueprints/{id}/set-current`, `POST/GET /api/admin/blueprints/{id}/domains`, `PUT/DELETE /api/admin/blueprints/{id}/domains/{domain_id}`.

- [ ] **Step 1: Fix the read `/api/domains` route** to pass `blueprint_id` (since `DomainOut` now requires it).

In `backend/app/api/taxonomy.py`, change the `domains` route's list comprehension to:

```python
return [
    DomainOut(id=d.id, blueprint_id=d.blueprint_id, number=d.number,
              name=d.name, weight_pct=d.weight_pct)
    for d in svc.list_domains(session)
]
```

Also add imports at top of `backend/app/api/taxonomy.py`:

```python
from app.schemas.taxonomy import (
    BindingIn,
    BlueprintIn,
    BlueprintOut,
    BlueprintUpdateIn,
    BookIn,
    ChapterIn,
    DomainIn,
    DomainOut,
    KnowledgePointIn,
    TagIn,
)
from app.services import taxonomy_admin as admin
```

- [ ] **Step 2: Write failing API tests** in `backend/tests/test_taxonomy_admin_api.py`

```python
"""HTTP tests for taxonomy admin (sub-project D)."""

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


def _headers(db_session, store, email="a@example.com", role=RoleName.system_admin, perms=None):
    user, _ = register_user(db_session, email=email, password="pw123456",
                            display_name="A", refresh_store=store)
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


def _bp_body(**kw):
    body = dict(version_label="2026-04-15", effective_date="2026-04-15",
                min_items=100, max_items=150, duration_minutes=180,
                passing_score=700, max_score=1000)
    body.update(kw)
    return body


def test_blueprint_create_and_get(client):
    c, store, db = client
    h = _headers(db, store, email="bp1@example.com")
    resp = c.post("/api/admin/blueprints", json=_bp_body(), headers=h)
    assert resp.status_code == 200, resp.text
    bpid = resp.json()["id"]
    got = c.get(f"/api/admin/blueprints/{bpid}", headers=h)
    assert got.status_code == 200
    assert got.json()["domains"] == []


def test_blueprint_create_validation_422(client):
    c, store, db = client
    h = _headers(db, store, email="bp2@example.com")
    assert c.post("/api/admin/blueprints", json=_bp_body(min_items=200, max_items=100),
                  headers=h).status_code == 422


def test_blueprint_set_current(client):
    c, store, db = client
    h = _headers(db, store, email="bp3@example.com")
    a = c.post("/api/admin/blueprints", json=_bp_body(version_label="a"), headers=h).json()["id"]
    b = c.post("/api/admin/blueprints", json=_bp_body(version_label="b"), headers=h).json()["id"]
    assert c.post(f"/api/admin/blueprints/{a}/set-current", headers=h).status_code == 200
    assert c.get(f"/api/admin/blueprints/{a}", headers=h).json()["is_current"] is True
    assert c.get(f"/api/admin/blueprints/{b}", headers=h).json()["is_current"] is False


def test_blueprint_list(client):
    c, store, db = client
    h = _headers(db, store, email="bp4@example.com")
    c.post("/api/admin/blueprints", json=_bp_body(version_label="a"), headers=h)
    c.post("/api/admin/blueprints", json=_bp_body(version_label="b"), headers=h)
    assert len(c.get("/api/admin/blueprints", headers=h).json()) == 2


def test_domain_create_and_list(client):
    c, store, db = client
    h = _headers(db, store, email="dm1@example.com")
    bpid = c.post("/api/admin/blueprints", json=_bp_body(), headers=h).json()["id"]
    resp = c.post(f"/api/admin/blueprints/{bpid}/domains",
                  json={"number": 1, "name": "D1", "weight_pct": 12}, headers=h)
    assert resp.status_code == 200, resp.text
    lst = c.get(f"/api/admin/blueprints/{bpid}/domains", headers=h)
    assert len(lst.json()) == 1


def test_domain_weight_422(client):
    c, store, db = client
    h = _headers(db, store, email="dm2@example.com")
    bpid = c.post("/api/admin/blueprints", json=_bp_body(), headers=h).json()["id"]
    assert c.post(f"/api/admin/blueprints/{bpid}/domains",
                  json={"number": 1, "name": "D1", "weight_pct": 200},
                  headers=h).status_code == 422


def test_admin_403_for_learner(client):
    c, store, db = client
    h = _headers(db, store, email="no@example.com", role=RoleName.individual_learner,
                 perms=["question:read", "practice:read", "exam:read"])
    assert c.post("/api/admin/blueprints", json=_bp_body(), headers=h).status_code == 403
```

- [ ] **Step 3: Run API tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_taxonomy_admin_api.py -v`
Expected: FAIL (routes not defined).

- [ ] **Step 4: Implement blueprint + domain routes** (append to `backend/app/api/taxonomy.py`)

```python
def _domain_out(d) -> DomainOut:
    return DomainOut(id=d.id, blueprint_id=d.blueprint_id, number=d.number,
                     name=d.name, weight_pct=d.weight_pct)


def _blueprint_out(session, bp) -> BlueprintOut:
    domains = [
        _domain_out(d) for d in session.execute(
            select(ExamDomain).where(ExamDomain.blueprint_id == bp.id)
            .order_by(ExamDomain.number)
        ).scalars().all()
    ]
    return BlueprintOut(
        id=bp.id, version_label=bp.version_label, effective_date=bp.effective_date,
        min_items=bp.min_items, max_items=bp.max_items, duration_minutes=bp.duration_minutes,
        passing_score=bp.passing_score, max_score=bp.max_score, is_current=bp.is_current,
        domains=domains,
    )
```

Add `from sqlalchemy import select` and `from app.models.taxonomy import ExamDomain` to the imports, and the routes:

```python
@router.post("/admin/blueprints", response_model=BlueprintOut)
def create_blueprint(
    body: BlueprintIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        bp = admin.create_blueprint(session, actor_id=current.user.id, payload=body)
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(bp)
    return _blueprint_out(session, bp)


@router.get("/admin/blueprints", response_model=list[BlueprintOut])
def list_blueprints(
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    return [_blueprint_out(session, bp) for bp in admin.list_blueprints(session)]


@router.get("/admin/blueprints/{blueprint_id}", response_model=BlueprintOut)
def get_blueprint(
    blueprint_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        bp = admin.get_blueprint(session, blueprint_id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="blueprint not found")
    return _blueprint_out(session, bp)


@router.put("/admin/blueprints/{blueprint_id}", response_model=BlueprintOut)
def update_blueprint(
    blueprint_id: uuid.UUID,
    body: BlueprintUpdateIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        bp = admin.update_blueprint(session, blueprint_id=blueprint_id,
                                    actor_id=current.user.id, payload=body)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="blueprint not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(bp)
    return _blueprint_out(session, bp)


@router.post("/admin/blueprints/{blueprint_id}/set-current", response_model=BlueprintOut)
def set_current_blueprint(
    blueprint_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        bp = admin.set_current_blueprint(session, blueprint_id=blueprint_id,
                                         actor_id=current.user.id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="blueprint not found")
    session.commit()
    session.refresh(bp)
    return _blueprint_out(session, bp)


@router.delete("/admin/blueprints/{blueprint_id}")
def delete_blueprint(
    blueprint_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        admin.delete_blueprint(session, blueprint_id=blueprint_id, actor_id=current.user.id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="blueprint not found")
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return {"deleted": str(blueprint_id)}


@router.post("/admin/blueprints/{blueprint_id}/domains", response_model=DomainOut)
def create_domain(
    blueprint_id: uuid.UUID,
    body: DomainIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        d = admin.create_domain(session, blueprint_id=blueprint_id,
                                actor_id=current.user.id, payload=body)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="blueprint not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    session.refresh(d)
    return _domain_out(d)


@router.get("/admin/blueprints/{blueprint_id}/domains", response_model=list[DomainOut])
def list_domains_for_blueprint(
    blueprint_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        domains = admin.list_domains_for_blueprint(session, blueprint_id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="blueprint not found")
    return [_domain_out(d) for d in domains]


@router.put("/admin/blueprints/{blueprint_id}/domains/{domain_id}", response_model=DomainOut)
def update_domain(
    blueprint_id: uuid.UUID,
    domain_id: uuid.UUID,
    body: DomainIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        d = admin.update_domain(session, blueprint_id=blueprint_id, domain_id=domain_id,
                                actor_id=current.user.id, payload=body)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="domain not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    session.refresh(d)
    return _domain_out(d)


@router.delete("/admin/blueprints/{blueprint_id}/domains/{domain_id}")
def delete_domain(
    blueprint_id: uuid.UUID,
    domain_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        admin.delete_domain(session, blueprint_id=blueprint_id, domain_id=domain_id,
                            actor_id=current.user.id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="domain not found")
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return {"deleted": str(domain_id)}
```

- [ ] **Step 5: Run API tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_taxonomy_admin_api.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/taxonomy.py backend/app/schemas/taxonomy.py backend/tests/test_taxonomy_admin_api.py
git commit -m "feat(taxonomy-admin): blueprint + domain HTTP routes"
```

---

### Task 8: HTTP API — books, chapters, knowledge points, bindings, tags

**Files:**
- Modify: `backend/app/api/taxonomy.py`
- Test: `backend/tests/test_taxonomy_admin_api.py` (append)

- [ ] **Step 1: Write failing API tests** (append to `test_taxonomy_admin_api.py`)

```python
def test_book_create_update_delete(client):
    c, store, db = client
    h = _headers(db, store, email="bk1@example.com")
    resp = c.post("/api/books", json={"title": "OSG"}, headers=h)
    assert resp.status_code == 200, resp.text
    bid = resp.json()["id"]
    put = c.put(f"/api/books/{bid}", json={"title": "OSG 10th"}, headers=h)
    assert put.json()["title"] == "OSG 10th"
    assert c.delete(f"/api/books/{bid}", headers=h).status_code == 200
    assert c.get("/api/books", headers=h).json() == []


def test_chapter_create(client):
    c, store, db = client
    h = _headers(db, store, email="ch1@example.com")
    bid = c.post("/api/books", json={"title": "B"}, headers=h).json()["id"]
    resp = c.post(f"/api/books/{bid}/chapters",
                  json={"order_index": 0, "title": "C1"}, headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "C1"


def test_knowledge_point_tree(client):
    c, store, db = client
    h = _headers(db, store, email="kp1@example.com")
    root = c.post("/api/knowledge-points", json={"name": "root"}, headers=h).json()
    child = c.post("/api/knowledge-points", json={"name": "child", "parent_id": root["id"]},
                   headers=h)
    assert child.status_code == 200, child.text
    # cycle -> 422
    bad = c.put(f"/api/knowledge-points/{root['id']}",
                json={"name": "root", "parent_id": child.json()["id"]}, headers=h)
    assert bad.status_code == 422


def test_tag_crud(client):
    c, store, db = client
    h = _headers(db, store, email="tg1@example.com")
    resp = c.post("/api/tags", json={"name": "crypto"}, headers=h)
    assert resp.status_code == 200, resp.text
    tid = resp.json()["id"]
    assert c.get("/api/tags", headers=h).json()[0]["name"] == "crypto"
    assert c.delete(f"/api/tags/{tid}", headers=h).status_code == 200


def test_kp_domain_binding(client):
    c, store, db = client
    h = _headers(db, store, email="bd1@example.com")
    bpid = c.post("/api/admin/blueprints", json=_bp_body(), headers=h).json()["id"]
    did = c.post(f"/api/admin/blueprints/{bpid}/domains",
                 json={"number": 1, "name": "D1", "weight_pct": 10}, headers=h).json()["id"]
    kid = c.post("/api/knowledge-points", json={"name": "KP"}, headers=h).json()["id"]
    bind = c.post(f"/api/admin/knowledge-points/{kid}/domains",
                  json={"domain_id": did}, headers=h)
    assert bind.status_code == 200, bind.text
    lst = c.get(f"/api/admin/knowledge-points/{kid}/domains", headers=h)
    assert len(lst.json()) == 1
    assert c.delete(f"/api/admin/knowledge-points/{kid}/domains/{did}", headers=h).status_code == 200
```

- [ ] **Step 2: Run API tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_taxonomy_admin_api.py -k "book or chapter or knowledge_point or tag or binding" -v`
Expected: FAIL.

- [ ] **Step 3: Implement remaining routes** (append to `backend/app/api/taxonomy.py`)

```python
@router.post("/books", response_model=BookOut)
def create_book(
    body: BookIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        book = admin.create_book(session, org_id=current.org_id,
                                 actor_id=current.user.id, payload=body)
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(book)
    return BookOut(id=book.id, title=book.title, edition=book.edition,
                   author=book.author, publisher=book.publisher)


@router.get("/books/{book_id}", response_model=BookOut)
def get_book(
    book_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:read")),
):
    try:
        book = admin.get_book(session, book_id=book_id, org_id=current.org_id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="book not found")
    return BookOut(id=book.id, title=book.title, edition=book.edition,
                   author=book.author, publisher=book.publisher)


@router.put("/books/{book_id}", response_model=BookOut)
def update_book(
    book_id: uuid.UUID,
    body: BookIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        book = admin.update_book(session, book_id=book_id, org_id=current.org_id,
                                 actor_id=current.user.id, payload=body)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="book not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(book)
    return BookOut(id=book.id, title=book.title, edition=book.edition,
                   author=book.author, publisher=book.publisher)


@router.delete("/books/{book_id}")
def delete_book(
    book_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        admin.delete_book(session, book_id=book_id, org_id=current.org_id,
                          actor_id=current.user.id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="book not found")
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return {"deleted": str(book_id)}


@router.post("/books/{book_id}/chapters", response_model=ChapterOut)
def create_chapter(
    book_id: uuid.UUID,
    body: ChapterIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        ch = admin.create_chapter(session, book_id=book_id, org_id=current.org_id,
                                  actor_id=current.user.id, payload=body)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="book not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(ch)
    return ChapterOut(id=ch.id, book_id=ch.book_id, order_index=ch.order_index, title=ch.title)


@router.put("/books/{book_id}/chapters/{chapter_id}", response_model=ChapterOut)
def update_chapter(
    book_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: ChapterIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        ch = admin.update_chapter(session, book_id=book_id, chapter_id=chapter_id,
                                  org_id=current.org_id, actor_id=current.user.id, payload=body)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="chapter not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(ch)
    return ChapterOut(id=ch.id, book_id=ch.book_id, order_index=ch.order_index, title=ch.title)


@router.delete("/books/{book_id}/chapters/{chapter_id}")
def delete_chapter(
    book_id: uuid.UUID,
    chapter_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        admin.delete_chapter(session, book_id=book_id, chapter_id=chapter_id,
                             org_id=current.org_id, actor_id=current.user.id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="chapter not found")
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return {"deleted": str(chapter_id)}


@router.post("/knowledge-points", response_model=KnowledgePointOut)
def create_knowledge_point(
    body: KnowledgePointIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        kp = admin.create_knowledge_point(session, actor_id=current.user.id, payload=body)
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="parent knowledge point not found")
    session.commit()
    session.refresh(kp)
    return KnowledgePointOut(id=kp.id, name=kp.name, description=kp.description,
                             parent_id=kp.parent_id)


@router.get("/knowledge-points/{kp_id}", response_model=KnowledgePointOut)
def get_knowledge_point(
    kp_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("question:read")),
):
    try:
        kp = admin.get_knowledge_point(session, kp_id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="knowledge point not found")
    return KnowledgePointOut(id=kp.id, name=kp.name, description=kp.description,
                             parent_id=kp.parent_id)


@router.put("/knowledge-points/{kp_id}", response_model=KnowledgePointOut)
def update_knowledge_point(
    kp_id: uuid.UUID,
    body: KnowledgePointIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        kp = admin.update_knowledge_point(session, kp_id=kp_id,
                                          actor_id=current.user.id, payload=body)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="knowledge point not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(kp)
    return KnowledgePointOut(id=kp.id, name=kp.name, description=kp.description,
                             parent_id=kp.parent_id)


@router.delete("/knowledge-points/{kp_id}")
def delete_knowledge_point(
    kp_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        admin.delete_knowledge_point(session, kp_id=kp_id, actor_id=current.user.id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="knowledge point not found")
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return {"deleted": str(kp_id)}


@router.post("/admin/knowledge-points/{kp_id}/domains", response_model=DomainOut)
def bind_kp_domain(
    kp_id: uuid.UUID,
    body: BindingIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        binding = admin.bind_kp_domain(session, kp_id=kp_id,
                                       actor_id=current.user.id, payload=body)
        session.refresh(binding)
        d = session.get(ExamDomain, binding.domain_id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="knowledge point or domain not found")
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return _domain_out(d)


@router.get("/admin/knowledge-points/{kp_id}/domains", response_model=list[DomainOut])
def list_kp_domains(
    kp_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        domains = admin.list_kp_domains(session, kp_id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="knowledge point not found")
    return [_domain_out(d) for d in domains]


@router.delete("/admin/knowledge-points/{kp_id}/domains/{domain_id}")
def unbind_kp_domain(
    kp_id: uuid.UUID,
    domain_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        admin.unbind_kp_domain(session, kp_id=kp_id, domain_id=domain_id,
                               actor_id=current.user.id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="binding not found")
    session.commit()
    return {"deleted": str(domain_id)}


@router.post("/tags", response_model=KnowledgePointOut)
def create_tag(
    body: TagIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        tag = admin.create_tag(session, actor_id=current.user.id, payload=body)
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    session.refresh(tag)
    return {"id": tag.id, "name": tag.name, "description": tag.description}


@router.get("/tags", response_model=list)
def list_tags(
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("question:read")),
):
    return [{"id": t.id, "name": t.name, "description": t.description}
            for t in admin.list_tags(session)]


@router.put("/tags/{tag_id}")
def update_tag(
    tag_id: uuid.UUID,
    body: TagIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        tag = admin.update_tag(session, tag_id=tag_id, actor_id=current.user.id, payload=body)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="tag not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    session.refresh(tag)
    return {"id": tag.id, "name": tag.name, "description": tag.description}


@router.delete("/tags/{tag_id}")
def delete_tag(
    tag_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        admin.delete_tag(session, tag_id=tag_id, actor_id=current.user.id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="tag not found")
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return {"deleted": str(tag_id)}
```

Note: `create_tag` uses `response_model=KnowledgePointOut` by mistake — the tag return is `{"id","name","description"}` which lacks `parent_id`. Use `response_model=dict` for both `create_tag` and the tag routes to avoid Pydantic validation errors. Replace the `create_tag` decorator with `@router.post("/tags", response_model=dict)`.

- [ ] **Step 4: Run all taxonomy admin API tests**

Run: `cd backend && source venv/bin/activate && pytest tests/test_taxonomy_admin_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/taxonomy.py backend/tests/test_taxonomy_admin_api.py
git commit -m "feat(taxonomy-admin): book/chapter/kp/binding/tag HTTP routes"
```

---

### Task 9: Full suite + CLAUDE.md update + finish branch

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && source venv/bin/activate && pytest -q`
Expected: all tests pass (122 prior + new taxonomy admin tests).

- [ ] **Step 2: Run migration drift test**

Run: `cd backend && source venv/bin/activate && pytest tests/test_migrations.py -v`
Expected: PASS (no schema changes this sub-project).

- [ ] **Step 3: Update CLAUDE.md Current State**

Update the "What exists now" sentence to add taxonomy admin, and the "What does NOT exist yet" line to remove "taxonomy write/admin". Change:

> plus read-only `/api/{domains,books,knowledge-points}` taxonomy API), idempotent seed ... (122 passing); frontend ...

to reflect taxonomy admin endpoints exist and bump test count. Change "interactive import, taxonomy write/admin — these are later sub-projects (D–H)" to "practice/exam APIs, CAT engine, analytics & admin UI, interactive import — these are later sub-projects (E–H)".

- [ ] **Step 4: Commit docs**

```bash
git add CLAUDE.md
git commit -m "docs: note taxonomy admin (sub-project D) complete"
```

- [ ] **Step 5: Finish the development branch**

Use the finishing-a-development-branch skill: verify tests pass, then merge `feat/taxonomy-admin` back to `master` locally (option 1), delete the feature branch. Do NOT touch the unstaged PRD edit.
