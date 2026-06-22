# Admin Backoffice API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver sub-project H2 — admin backoffice APIs for FR-ADMIN-03..07 (user/class management, CAT-param versioning, content-quality queue, audit-log viewer, operational reports).

**Architecture:** New `admin` bounded concern (service + thin router + schemas) mirroring sub-projects D/G/H1. Three new tables (`cat_params_versions`, `classes`, `class_memberships`), one new permission (`admin:view_reports`), a one-line exam.py integration to snapshot current CAT params. All admin reads are org-scoped for org_admin and global for system_admin via a single `_admin_org_scope` helper.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, PostgreSQL 16 (JSONB, FKs, unique constraints), Redis 7 (unchanged).

## Global Constraints

Carry these verbatim into every task. They bind the whole sub-project.

- **Tests use the real `cissp_test` DB** (per-test SAVEPOINT rollback, `Base.metadata.create_all`). NEVER touch the dev `cissp` DB. Migration drift tested against `cissp_migtest`.
- **Service-layer backend**: no business logic in route handlers; `app/api/admin.py` is thin. Caller commits after mutations; `log_audit` flushes only (does NOT commit); read-only GETs do NOT commit.
- **Admin scoping**: `_admin_org_scope(current)` returns `None` for `system_admin` (global) and `current.org_id` for everyone else. Every admin query applies this filter. Out-of-scope targets return 404 (not 403), to avoid leaking existence.
- **Permissions**: users+classes → `admin:manage_users`; CAT params → `admin:manage_taxonomy`; quality queue → `question:publish`; audit viewer → `admin:view_audit`; reports → `admin:view_reports` (NEW). Gate each route with `require_permission(code)`.
- **org_admin cross-org guard**: if an org_admin supplies an `org_id` query param (on `/audit-logs` or `/reports/summary`) that is not their own → 403.
- **Native PG ENUM**: H2 adds NO new ENUM types. `CatParamsVersion.params` is JSONB. `Class`/`ClassMembership` use only existing ENUMs (none). Migration upgrade creates 3 tables; downgrade drops them in reverse. No `CREATE/DROP TYPE`.
- **Soft delete**: `Class` uses `SoftDeleteMixin` (`deleted_at`); queries filter `not_deleted(Class)`. ClassMembership is hard-deleted (CASCADE on class delete).
- **Tenant scoping**: `Class` is `organization_id`-scoped NOT NULL (TenantScopedMixin). `CatParamsVersion` is GLOBAL (exam config is data, shared across orgs) — no organization_id.
- **Audit every mutation**: role/status changes → `AuditAction.permission_change`; CAT-params set-current/create-current → `AuditAction.config_change`; class CRUD + feedback resolution → `AuditAction.edit` (class delete → `archive`). All via `log_audit`.
- **CAT params historical integrity**: exam.py snapshots `dict(current_version.params)` (or `DEFAULT_PARAMS` fallback) into `ExamSession.config["cat_params"]` at session creation. Later edits to CatParamsVersion never change existing sessions. Existing CAT tests must still pass (fallback == DEFAULT_PARAMS when no version seeded).
- **window_days**: `/reports/summary` accepts `{30, 90}` only, default 30, else 422 (matches analytics trend).
- **Handler names must NOT shadow `get_session`** (the DB-session dependency import). Use `list_*`, `get_*` with specific nouns (e.g. `get_user_detail`, `list_audit_logs`).
- **Migration head**: `down_revision = "145d056cbfbe"` (current head). Single linear new head.
- **uq_users_email_lower**: the hand-written functional index is intentionally omitted from migration drops (matches `50a14663f11a` / `145d056cbfbe` convention). Do NOT add it to the new migration.
- **The uncommitted working-tree edit to `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` is NOT ours** — never stage/commit/clobber it. Stage only intended files per task.
- **Validation errors**: service raises `ValidationError`/`NotFound`/`ConflictError` (define in `app/services/admin.py`); router maps to 422/404/409 — mirrors `taxonomy_admin`/`practice`/`exam`.

---

### Task 1: Models — CatParamsVersion, Class, ClassMembership + migration + registration

**Files:**
- Modify: `backend/app/models/admin.py` — add `CatParamsVersion`.
- Modify: `backend/app/models/auth.py` — add `Class`, `ClassMembership`.
- Modify: `backend/app/models/__init__.py` — register the three new models in imports + `__all__`.
- Create: `backend/app/alembic/versions/<new>_admin_backoffice_tables.py`
- Test: `backend/tests/test_admin_models.py` (new)

**Interfaces:**
- Produces: `CatParamsVersion` (id, version_label, effective_date, is_current, params JSONB, timestamps), `Class` (id, organization_id, name, description, instructor_id, deleted_at, timestamps), `ClassMembership` (id, class_id, user_id, timestamps, unique(class_id,user_id)).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_admin_models.py`:

```python
from datetime import date

from app.models.admin import CatParamsVersion
from app.models.auth import Class, ClassMembership, Organization, User


def test_cat_params_version_persists(db_session):
    org = Organization(name="Org", slug="org", kind="personal", status="active")
    db_session.add(org); db_session.flush()
    cpv = CatParamsVersion(
        version_label="v1", effective_date=date(2026, 1, 1),
        is_current=True, params={"k0": 0.5, "decay": 0.1, "base_se": 1.0, "early_stop_enabled": True},
    )
    db_session.add(cpv); db_session.flush()
    got = db_session.get(CatParamsVersion, cpv.id)
    assert got.params["k0"] == 0.5
    assert got.is_current is True


def test_class_and_membership_persist(db_session):
    org = Organization(name="Org", slug="org2", kind="personal", status="active")
    db_session.add(org); db_session.flush()
    u = User(email="c@example.com", status="active", default_organization_id=org.id)
    db_session.add(u); db_session.flush()
    cls = Class(organization_id=org.id, name="Section A", description="d", instructor_id=u.id)
    db_session.add(cls); db_session.flush()
    m = ClassMembership(class_id=cls.id, user_id=u.id)
    db_session.add(m); db_session.flush()
    assert db_session.get(Class, cls.id).name == "Section A"
    assert db_session.get(ClassMembership, m.id).user_id == u.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_models.py -v`
Expected: FAIL — `cannot import name 'CatParamsVersion'`.

- [ ] **Step 3: Add the models**

In `backend/app/models/admin.py`, after `SchemaMeta`, add:

```python
from datetime import date

from sqlalchemy import Boolean, Date

from sqlalchemy.dialects.postgresql import JSONB
```
(merge these imports into the existing import block at the top of the file — `Date`, `Boolean` from `sqlalchemy`, `JSONB` already imported; keep `datetime`).

Then append after `SchemaMeta`:

```python
class CatParamsVersion(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "cat_params_versions"

    version_label: Mapped[str] = mapped_column(String(50), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
```

In `backend/app/models/auth.py`, append after `OrganizationMembership`:

```python
class Class(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "classes"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    instructor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )


class ClassMembership(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "class_memberships"
    __table_args__ = (
        UniqueConstraint("class_id", "user_id", name="uq_class_membership"),
    )

    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
```

Ensure `TenantScopedMixin` and `SoftDeleteMixin` are imported in `auth.py` (add `from app.db.base import ... TenantScopedMixin, SoftDeleteMixin` if missing — check `app/models/question.py` for the exact import line to copy).

In `backend/app/models/__init__.py`, add to the `admin` import line:
```python
from app.models.admin import AuditLog, CatParamsVersion, SchemaMeta  # noqa: F401
```
Add to the `auth` import block: `Class`, `ClassMembership`. Add all three to `__all__`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_models.py -v`
Expected: 2 passed.

- [ ] **Step 5: Create the migration**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && alembic revision --autogenerate -m "admin backoffice tables"`
Open the generated file. Verify `down_revision = "145d056cbfbe"`. Verify it creates `cat_params_versions`, `classes`, `class_memberships` only (no spurious drops — if autogenerate tries to drop `uq_users_email_lower` or `_test_*` tables, delete those lines and add a `# NOTE: uq_users_email_lower intentionally not dropped` comment). Ensure `classes` has `organization_id` FK NOT NULL and `deleted_at` nullable; `class_memberships` has the `uq_class_membership` unique constraint. Verify the `downgrade()` drops the three tables in reverse dependency order (`class_memberships`, `classes`, `cat_params_versions`).

- [ ] **Step 6: Run migration drift test**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_migrations.py -v`
Expected: 2 passed (zero drift).

- [ ] **Step 7: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/models/admin.py backend/app/models/auth.py backend/app/models/__init__.py backend/app/alembic/versions backend/tests/test_admin_models.py
git commit -m "feat(admin): CatParamsVersion + Class/ClassMembership models + migration"
```

---

### Task 2: Seed — add admin:view_reports permission + matrix + bump seed_version

**Files:**
- Modify: `backend/app/db/seed.py`
- Test: `backend/tests/test_seed.py` (extend)

**Interfaces:**
- Produces: `admin:view_reports` permission row; assigned to `org_admin` and `system_admin`; `SEED_VERSION = "4"`.

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_seed.py`, find the existing seed test and add (or extend) assertions:

```python
def test_seed_includes_reports_permission(db_session):
    from app.models.auth import Permission, Role, RolePermission, RoleName
    from app.db.seed import run_seed
    run_seed(db_session)
    rep = db_session.execute(
        select(Permission).filter_by(code="admin:view_reports")
    ).scalar_one()
    assert rep is not None
    for name in (RoleName.org_admin, RoleName.system_admin):
        role = db_session.execute(select(Role).filter_by(name=name)).scalar_one()
        link = db_session.execute(
            select(RolePermission).filter_by(role_id=role.id, permission_id=rep.id)
        ).scalar_one()
        assert link is not None
    # instructor + content_editor + individual_learner do NOT get it
    for name in (RoleName.individual_learner, RoleName.instructor, RoleName.content_editor):
        role = db_session.execute(select(Role).filter_by(name=name)).scalar_one()
        link = db_session.execute(
            select(RolePermission).filter_by(role_id=role.id, permission_id=rep.id)
        ).scalar_one_or_none()
        assert link is None
```
(Use the imports already present at the top of `test_seed.py`; `select` comes from sqlalchemy. Match the file's existing fixture style.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_seed.py -v -k reports`
Expected: FAIL — `admin:view_reports` not found.

- [ ] **Step 3: Update the seed**

In `backend/app/db/seed.py`:
- Change `SEED_VERSION = "3"` to `SEED_VERSION = "4"`.
- Append to `PERMISSIONS` (after `admin:view_audit`):
  ```python
      ("admin:view_reports", "View operational reports"),
  ```
- In `ROLE_PERMISSIONS`, append `"admin:view_reports"` to the `org_admin` list (after `"admin:view_audit"`) and it is automatically included for `system_admin` via the `[code for code, _ in PERMISSIONS]` comprehension.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_seed.py -v`
Expected: all seed tests pass (including the new one and idempotency).

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/db/seed.py backend/tests/test_seed.py
git commit -m "feat(seed): add admin:view_reports permission (org_admin + system_admin)"
```

---

### Task 3: Schemas — `app/schemas/admin.py`

**Files:**
- Create: `backend/app/schemas/admin.py`
- Test: `backend/tests/test_admin_schemas.py` (new, light)

**Interfaces:**
- Produces: all schemas listed in the design doc (UserOut, UserStatusIn, UserRolesIn, ClassOut, ClassIn, ClassMemberOut, CatParamsVersionOut, CatParams + CatParamsIn, FeedbackOut, FeedbackResolveIn, QualityDashboardOut, LowAccuracyQuestionOut, MissingExplanationQuestionOut, AuditLogOut, PaginatedAudit, ReportSummaryOut).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_admin_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.schemas.admin import CatParams, CatParamsIn, UserStatusIn, ReportSummaryOut


def test_cat_params_valid():
    p = CatParams(k0=0.5, decay=0.1, base_se=1.0, early_stop_enabled=True)
    assert p.k0 == 0.5


@pytest.mark.parametrize("bad", [
    {"k0": 0, "decay": 0.1, "base_se": 1.0, "early_stop_enabled": True},      # k0 must be >0
    {"k0": 0.5, "decay": -1, "base_se": 1.0, "early_stop_enabled": True},     # decay >=0
    {"k0": 0.5, "decay": 0.1, "base_se": 0, "early_stop_enabled": True},      # base_se >0
])
def test_cat_params_rejects_invalid(bad):
    with pytest.raises(ValidationError):
        CatParams(**bad)


def test_report_summary_optional_top_error_questions():
    r = ReportSummaryOut(
        scope="global", window_days=30, active_users=0, practice_session_count=0,
        exam_session_count=0, total_answers=0, correct_answers=0, accuracy=0.0,
        published_question_count=0, used_question_count=0, question_bank_usage_pct=0.0,
        top_error_questions=[],
    )
    assert r.top_error_questions == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_schemas.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the schemas**

Create `backend/app/schemas/admin.py`:

```python
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import QuestionFeedbackStatus, RoleName, UserStatus


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    status: str
    default_organization_id: uuid.UUID | None
    roles: list[str]


class UserStatusIn(BaseModel):
    status: UserStatus


class UserRolesIn(BaseModel):
    role_names: list[RoleName]


class ClassOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    instructor_id: uuid.UUID | None
    organization_id: uuid.UUID
    member_count: int


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    instructor_id: uuid.UUID | None = None


class ClassMemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str | None


class CatParamsVersionOut(BaseModel):
    id: uuid.UUID
    version_label: str
    effective_date: date
    is_current: bool
    params: dict


class CatParams(BaseModel):
    k0: float = Field(gt=0)
    decay: float = Field(ge=0)
    base_se: float = Field(gt=0)
    early_stop_enabled: bool = True


class CatParamsIn(BaseModel):
    version_label: str = Field(min_length=1, max_length=50)
    effective_date: date
    params: CatParams
    set_current: bool = True


class FeedbackOut(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    reporter_id: uuid.UUID | None
    feedback_type: str
    comment: str | None
    status: str
    created_at: datetime


class FeedbackResolveIn(BaseModel):
    status: QuestionFeedbackStatus
    comment: str | None = None

    @field_validator("status")
    @classmethod
    def _must_be_terminal(cls, v: QuestionFeedbackStatus) -> QuestionFeedbackStatus:
        if v not in (QuestionFeedbackStatus.resolved, QuestionFeedbackStatus.wont_fix):
            raise ValueError("status must be resolved or wont_fix")
        return v


class QualityDashboardOut(BaseModel):
    open_feedback_count: int
    low_accuracy_question_count: int
    missing_explanation_count: int
    disputed_question_count: int


class LowAccuracyQuestionOut(BaseModel):
    question_id: uuid.UUID
    stem: str
    answered: int
    correct: int
    accuracy: float


class MissingExplanationQuestionOut(BaseModel):
    question_id: uuid.UUID
    stem: str
    status: str


class AuditLogOut(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    action: str
    actor_id: uuid.UUID | None
    organization_id: uuid.UUID | None
    entity_type: str | None
    entity_id: str | None
    details: dict | None
    ip_address: str | None


class PaginatedAudit(BaseModel):
    items: list[AuditLogOut]
    total: int
    limit: int
    offset: int


class ReportSummaryOut(BaseModel):
    scope: str
    window_days: int
    active_users: int
    practice_session_count: int
    exam_session_count: int
    total_answers: int
    correct_answers: int
    accuracy: float
    published_question_count: int
    used_question_count: int
    question_bank_usage_pct: float
    top_error_questions: list[LowAccuracyQuestionOut]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_schemas.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/schemas/admin.py backend/tests/test_admin_schemas.py
git commit -m "feat(admin): request/response schemas"
```

---

### Task 4: Service — user management + classes (FR-ADMIN-03)

**Files:**
- Create: `backend/app/services/admin.py`
- Test: `backend/tests/test_admin_service.py` (new)

**Interfaces:**
- Consumes: `CurrentUser` (from `app/dependencies`), `log_audit` (from `app.services.audit`), models `User/Role/Permission/RolePermission/OrganizationMembership/Class/ClassMembership`, `not_deleted` (from `app.db.queries`).
- Produces: `admin.py` with `ValidationError/NotFound/ConflictError`, `_admin_org_scope`, and the user+class functions: `list_users`, `get_user`, `set_user_status`, `set_user_roles`, `list_classes`, `create_class`, `get_class`, `update_class`, `delete_class`, `list_class_members`, `add_class_member`, `remove_class_member`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_admin_service.py`. Use module-level seed helpers matching `test_exam_service.py`/`test_analytics.py` conventions (a `_org`/`_user`/`_role` helper, a `current` CurrentUser built manually). Seed two orgs, users with memberships, roles. Tests:

```python
import uuid
from dataclasses import dataclass

from app.dependencies import CurrentUser
from app.models.auth import Organization, User, Role, RoleName, OrganizationMembership
from app.services import admin as svc


def _org(db, slug):
    o = Organization(name=slug, slug=slug, kind="personal", status="active")
    db.add(o); db.flush(); return o


def _user(db, email, org, status="active"):
    u = User(email=email, status=status, default_organization_id=org.id)
    db.add(u); db.flush()
    db.add(OrganizationMembership(user_id=u.id, organization_id=org.id,
            role_id=db.query(Role).filter_by(name=RoleName.individual_learner).one().id))
    db.flush(); return u


def _current(db, org, role_name=RoleName.org_admin):
    role = db.query(Role).filter_by(name=role_name).one()
    return CurrentUser(user=_user(db, f"admin-{org.slug}@x.com", org),
                       org_id=org.id, roles=[role_name.value],
                       perms=[c for c, _ in __import__("app.db.seed", fromlist=["PERMISSIONS"]).PERMISSIONS])


def test_list_users_org_scoped(db_session):
    db = db_session
    o1, o2 = _org(db, "o1"), _org(db, "o2")
    _user(db, "a@x.com", o1); _user(db, "b@x.com", o2)
    cur = _current(db, o1)
    users, total = svc.list_users(db, current=cur, search=None, limit=50, offset=0)
    emails = {u.email for u in users}
    assert "a@x.com" in emails and "b@x.com" not in emails
    assert total >= 1


def test_org_admin_cannot_get_other_org_user(db_session):
    db = db_session
    o1, o2 = _org(db, "o1"), _org(db, "o2")
    target = _user(db, "x@x.com", o2)
    cur = _current(db, o1)
    import pytest
    with pytest.raises(svc.NotFound):
        svc.get_user(db, current=cur, user_id=target.id)


def test_set_user_status_audits(db_session):
    db = db_session
    o1 = _org(db, "o1")
    target = _user(db, "t@x.com", o1)
    cur = _current(db, o1)
    out = svc.set_user_status(db, current=cur, user_id=target.id, status="disabled")
    assert out.status == "disabled"
    db.flush()
    from app.models.admin import AuditLog
    logs = db.query(AuditLog).filter_by(entity_type="user", entity_id=str(target.id)).all()
    assert any(l.action.value == "permission_change" for l in logs)


def test_set_user_roles_scoped_to_org(db_session):
    db = db_session
    o1 = _org(db, "o1")
    target = _user(db, "t@x.com", o1)
    cur = _current(db, o1)
    out = svc.set_user_roles(db, current=cur, user_id=target.id,
                             role_names=[RoleName.instructor])
    assert out.roles == ["instructor"]
    # membership role updated
    m = db.query(OrganizationMembership).filter_by(user_id=target.id, organization_id=o1.id).one()
    assert m.role_id == db.query(Role).filter_by(name=RoleName.instructor).one().id


def test_class_crud_org_scoped(db_session):
    db = db_session
    o1 = _org(db, "o1")
    cur = _current(db, o1)
    c = svc.create_class(db, current=cur, payload=__import__("app.schemas.admin", fromlist=["ClassIn"]).ClassIn(name="Sec A"))
    assert c.organization_id == o1.id
    got = svc.get_class(db, current=cur, class_id=c.id)
    assert got.name == "Sec A"
    upd = svc.update_class(db, current=cur, class_id=c.id,
                           payload=__import__("app.schemas.admin", fromlist=["ClassIn"]).ClassIn(name="Sec B"))
    assert upd.name == "Sec B"
    svc.delete_class(db, current=cur, class_id=c.id)
    import pytest
    with pytest.raises(svc.NotFound):
        svc.get_class(db, current=cur, class_id=c.id)


def test_class_membership(db_session):
    db = db_session
    o1 = _org(db, "o1")
    target = _user(db, "m@x.com", o1)
    cur = _current(db, o1)
    c = svc.create_class(db, current=cur, payload=__import__("app.schemas.admin", fromlist=["ClassIn"]).ClassIn(name="Sec A"))
    svc.add_class_member(db, current=cur, class_id=c.id, user_id=target.id)
    members = svc.list_class_members(db, current=cur, class_id=c.id)
    assert any(m.user_id == target.id for m in members)
    svc.remove_class_member(db, current=cur, class_id=c.id, user_id=target.id)
    assert not any(m.user_id == target.id for m in svc.list_class_members(db, current=cur, class_id=c.id))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_service.py -v`
Expected: FAIL — module `app.services.admin` not found.

- [ ] **Step 3: Write the service (user + class portion)**

Create `backend/app/services/admin.py`. Start with exceptions + scoping helper + user + class functions. (Quality/audit/report/cat-params functions are added in later tasks; do NOT stub them yet.)

```python
"""Admin backoffice service (FR-ADMIN-03..07).

All queries are org-scoped for org_admin (current.org_id) and global for
system_admin (None scope). Out-of-scope targets raise NotFound (not 403) to
avoid leaking existence. Mutations write AuditLog via log_audit (flush only;
caller commits).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.queries import not_deleted
from app.dependencies import CurrentUser
from app.models.admin import AuditLog
from app.models.auth import (
    Class,
    ClassMembership,
    OrganizationMembership,
    Role,
    RoleName,
    User,
)
from app.models.enums import AuditAction, UserStatus
from app.schemas.admin import (
    ClassIn,
    ClassMemberOut,
    ClassOut,
    UserOut,
    UserRolesIn,
    UserStatusIn,
)
from app.services.audit import log_audit


class ValidationError(Exception):
    pass


class NotFound(Exception):
    pass


class ConflictError(Exception):
    pass


_REPORTS_PERM = "admin:view_reports"
_SYSTEM_ADMIN = RoleName.system_admin.value


def _admin_org_scope(current: CurrentUser) -> uuid.UUID | None:
    """None for system_admin (global); org_id for everyone else."""
    if _SYSTEM_ADMIN in current.roles:
        return None
    return current.org_id


def _ensure_same_org(current: CurrentUser, org_id: uuid.UUID | None) -> None:
    """For org_admin, reject queries targeting another org."""
    scope = _admin_org_scope(current)
    if scope is not None and org_id is not None and org_id != scope:
        raise ValidationError("cannot target another organization")


def _user_out(session: Session, user: User, org_id: uuid.UUID) -> UserOut:
    role_names = [
        r.name.value
        for r in session.execute(
            select(Role.name)
            .join(OrganizationMembership, OrganizationMembership.role_id == Role.id)
            .where(OrganizationMembership.user_id == user.id,
                   OrganizationMembership.organization_id == org_id)
        ).scalars()
    ]
    return UserOut(
        id=user.id, email=user.email, display_name=user.display_name,
        status=user.status.value, default_organization_id=user.default_organization_id,
        roles=role_names,
    )


def _resolve_scope_org(current: CurrentUser, user: User) -> uuid.UUID:
    """Org to use for role listing: admin scope (org_admin) or user's default org (system_admin)."""
    scope = _admin_org_scope(current)
    return scope if scope is not None else (user.default_organization_id or current.org_id)


# ---- FR-ADMIN-03: users ----

def list_users(session, *, current, search=None, limit=50, offset=0):
    scope = _admin_org_scope(current)
    q = select(User).join(OrganizationMembership,
                          OrganizationMembership.user_id == User.id)
    if scope is not None:
        q = q.where(OrganizationMembership.organization_id == scope)
    if search:
        q = q.where(or_(User.email.ilike(f"%{search}%"),
                        User.display_name.ilike(f"%{search}%")))
    total = session.execute(
        select(func.count()).select_from(q.subquery())
    ).scalar_one()
    rows = session.execute(
        q.order_by(User.email).limit(limit).offset(offset)
    ).scalars().unique().all()
    out = [_user_out(session, u, _resolve_scope_org(current, u)) for u in rows]
    return out, total


def get_user(session, *, current, user_id):
    user = session.get(User, user_id)
    if user is None:
        raise NotFound("user not found")
    scope = _admin_org_scope(current)
    if scope is not None:
        in_org = session.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.organization_id == scope,
            )
        ).scalar_one_or_none()
        if in_org is None:
            raise NotFound("user not found")
    return _user_out(session, user, _resolve_scope_org(current, user))


def set_user_status(session, *, current, user_id, status: UserStatus):
    user = session.get(User, user_id)
    if user is None:
        raise NotFound("user not found")
    get_user(session, current=current, user_id=user_id)  # scope check -> NotFound
    user.status = status
    session.flush()
    log_audit(session, action=AuditAction.permission_change, actor_id=current.user.id,
              organization_id=current.org_id, entity_type="user", entity_id=str(user_id),
              details={"status": status.value})
    return _user_out(session, user, _resolve_scope_org(current, user))


def set_user_roles(session, *, current, user_id, role_names: list[RoleName]):
    user = session.get(User, user_id)
    if user is None:
        raise NotFound("user not found")
    org_id = _resolve_scope_org(current, user)
    # scope check
    if _admin_org_scope(current) is not None:
        get_user(session, current=current, user_id=user_id)
    role_ids = []
    for name in role_names:
        r = session.execute(select(Role).where(Role.name == name)).scalar_one_or_none()
        if r is None:
            raise ValidationError(f"unknown role {name}")
        role_ids.append(r.id)
    # replace memberships in this org only
    session.execute(
        OrganizationMembership.__table__.delete().where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == org_id,
        )
    )
    for rid in role_ids:
        session.add(OrganizationMembership(user_id=user_id, organization_id=org_id, role_id=rid))
    session.flush()
    log_audit(session, action=AuditAction.permission_change, actor_id=current.user.id,
              organization_id=org_id, entity_type="user", entity_id=str(user_id),
              details={"roles": [n.value for n in role_names]})
    return _user_out(session, user, org_id)


# ---- FR-ADMIN-03: classes ----

def _class_out(session, cls: Class) -> ClassOut:
    count = session.execute(
        select(func.count()).select_from(
            select(ClassMembership).where(ClassMembership.class_id == cls.id).subquery()
        )
    ).scalar_one()
    return ClassOut(id=cls.id, name=cls.name, description=cls.description,
                    instructor_id=cls.instructor_id, organization_id=cls.organization_id,
                    member_count=count)


def _scoped_class(session, current, class_id) -> Class:
    q = select(Class).where(Class.id == class_id, not_deleted(Class))
    scope = _admin_org_scope(current)
    if scope is not None:
        q = q.where(Class.organization_id == scope)
    cls = session.execute(q).scalar_one_or_none()
    if cls is None:
        raise NotFound("class not found")
    return cls


def list_classes(session, *, current, limit=50, offset=0):
    q = select(Class).where(not_deleted(Class))
    scope = _admin_org_scope(current)
    if scope is not None:
        q = q.where(Class.organization_id == scope)
    total = session.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = session.execute(q.order_by(Class.name).limit(limit).offset(offset)).scalars().all()
    return [_class_out(session, c) for c in rows], total


def create_class(session, *, current, payload: ClassIn) -> ClassOut:
    scope = _admin_org_scope(current) or current.org_id
    cls = Class(organization_id=scope, name=payload.name,
                description=payload.description, instructor_id=payload.instructor_id)
    session.add(cls); session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=current.user.id, organization_id=scope,
              entity_type="class", entity_id=str(cls.id), details={"name": payload.name})
    return _class_out(session, cls)


def get_class(session, *, current, class_id) -> ClassOut:
    return _class_out(session, _scoped_class(session, current, class_id))


def update_class(session, *, current, class_id, payload: ClassIn) -> ClassOut:
    cls = _scoped_class(session, current, class_id)
    cls.name = payload.name
    cls.description = payload.description
    cls.instructor_id = payload.instructor_id
    session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=current.user.id,
              organization_id=cls.organization_id, entity_type="class",
              entity_id=str(cls.id), details={"name": payload.name})
    return _class_out(session, cls)


def delete_class(session, *, current, class_id) -> None:
    cls = _scoped_class(session, current, class_id)
    from datetime import datetime, timezone
    cls.deleted_at = datetime.now(timezone.utc)
    session.flush()
    log_audit(session, action=AuditAction.archive, actor_id=current.user.id,
              organization_id=cls.organization_id, entity_type="class",
              entity_id=str(cls.id), details={"name": cls.name})


def list_class_members(session, *, current, class_id):
    cls = _scoped_class(session, current, class_id)
    rows = session.execute(
        select(User, ClassMembership)
        .join(User, User.id == ClassMembership.user_id)
        .where(ClassMembership.class_id == cls.id)
        .order_by(User.email)
    ).all()
    return [ClassMemberOut(user_id=u.id, email=u.email, display_name=u.display_name)
            for u, _ in rows]


def add_class_member(session, *, current, class_id, user_id) -> None:
    cls = _scoped_class(session, current, class_id)
    # user must be in the class's org
    scope = _admin_org_scope(current)
    org_filter = scope if scope is not None else cls.organization_id
    m = session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == org_filter,
        )
    ).scalar_one_or_none()
    if m is None:
        raise NotFound("user not found")
    existing = session.execute(
        select(ClassMembership).where(ClassMembership.class_id == cls.id,
                                      ClassMembership.user_id == user_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("already a member")
    session.add(ClassMembership(class_id=cls.id, user_id=user_id)); session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=current.user.id,
              organization_id=cls.organization_id, entity_type="class_member",
              entity_id=str(cls.id), details={"user_id": str(user_id)})


def remove_class_member(session, *, current, class_id, user_id) -> None:
    cls = _scoped_class(session, current, class_id)
    m = session.execute(
        select(ClassMembership).where(ClassMembership.class_id == cls.id,
                                      ClassMembership.user_id == user_id)
    ).scalar_one_or_none()
    if m is None:
        raise NotFound("membership not found")
    session.delete(m); session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=current.user.id,
              organization_id=cls.organization_id, entity_type="class_member",
              entity_id=str(cls.id), details={"removed_user_id": str(user_id)})
```

Note: `set_user_status` and `set_user_roles` take `status: UserStatus` / `role_names: list[RoleName]` — the router passes `payload.status` / `payload.role_names` from the validated Pydantic models. Adjust the test's `set_user_status(..., status="disabled")` call: the test passes a string; update the test to pass `UserStatus.disabled` (import `UserStatus`). Fix the test now:

In `test_admin_service.py`, change `svc.set_user_status(db, current=cur, user_id=target.id, status="disabled")` to:
```python
from app.models.enums import UserStatus
svc.set_user_status(db, current=cur, user_id=target.id, status=UserStatus.disabled)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_service.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/services/admin.py backend/tests/test_admin_service.py
git commit -m "feat(admin): user + class management service (FR-ADMIN-03)"
```

---

### Task 5: Service — CAT params (FR-ADMIN-04) + exam.py integration

**Files:**
- Modify: `backend/app/services/admin.py` — add CAT-params functions.
- Modify: `backend/app/services/exam.py` — snapshot current CatParamsVersion into CAT session config.
- Test: `backend/tests/test_admin_service.py` (extend) + `backend/tests/test_exam_service.py` (extend, one assertion).

**Interfaces:**
- Consumes: `CatParamsVersion` model, `cat_engine.DEFAULT_PARAMS`, `exam.py` CAT-create path.
- Produces: `list_cat_params`, `create_cat_params`, `set_current_cat_params`, `get_current_cat_params`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_admin_service.py`:

```python
from datetime import date
from app.models.admin import CatParamsVersion
from app.schemas.admin import CatParams, CatParamsIn


def _sysadmin_current(db, org):
    return _current(db, org, role_name=RoleName.system_admin)


def test_create_cat_params_sets_current_and_unsets_siblings(db_session):
    db = db_session
    o1 = _org(db, "o1")
    cur = _sysadmin_current(db, o1)
    v1 = svc.create_cat_params(db, current=cur, payload=CatParamsIn(
        version_label="v1", effective_date=date(2026, 1, 1),
        params=CatParams(k0=0.5, decay=0.1, base_se=1.0)))
    assert v1.is_current is True
    v2 = svc.create_cat_params(db, current=cur, payload=CatParamsIn(
        version_label="v2", effective_date=date(2026, 2, 1),
        params=CatParams(k0=0.4, decay=0.1, base_se=1.0)))
    db.flush()
    assert v2.is_current is True
    assert db.get(CatParamsVersion, v1.id).is_current is False


def test_set_current_cat_params(db_session):
    db = db_session
    o1 = _org(db, "o1")
    cur = _sysadmin_current(db, o1)
    v1 = svc.create_cat_params(db, current=cur, payload=CatParamsIn(
        version_label="v1", effective_date=date(2026, 1, 1),
        params=CatParams(k0=0.5, decay=0.1, base_se=1.0), set_current=False))
    v2 = svc.create_cat_params(db, current=cur, payload=CatParamsIn(
        version_label="v2", effective_date=date(2026, 2, 1),
        params=CatParams(k0=0.4, decay=0.1, base_se=1.0), set_current=True))
    out = svc.set_current_cat_params(db, current=cur, version_id=v1.id)
    assert out.is_current is True
    assert db.get(CatParamsVersion, v2.id).is_current is False


def test_get_current_cat_params_fallback_none(db_session):
    db = db_session
    assert svc.get_current_cat_params(db) is None
```

And in `backend/tests/test_exam_service.py`, add a test that a CAT session snapshots a configured CatParamsVersion (seed one, create a CAT session, assert `config["cat_params"]["k0"]` equals the configured value). Use the existing `_seed_cat_pool` fixture pattern from `test_exam_api.py` (copy the helper into the service test if not already present). The test:

```python
def test_cat_session_snapshots_current_cat_params(db_session):
    from datetime import date
    from app.models.admin import CatParamsVersion
    from app.schemas.admin import CatParams
    from app.services import admin as asvc
    from app.services import exam as esvc
    # ... seed blueprint + pool + actor exactly as the existing CAT service test ...
    cpv = CatParamsVersion(version_label="v1", effective_date=date(2026,1,1),
                           is_current=True,
                           params={"k0": 0.42, "decay": 0.1, "base_se": 1.0, "early_stop_enabled": True})
    db_session.add(cpv); db_session.flush()
    es = esvc.create_session(db_session, kind="cat", actor_id=actor.id, org_id=org.id)
    assert es.config["cat_params"]["k0"] == 0.42
```
(Match the existing CAT service test's exact `create_session` signature and seed fixtures — read `test_exam_service.py` first and mirror it. If the existing CAT service test uses a different signature, use that one verbatim.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_service.py tests/test_exam_service.py -v -k "cat_params or cat_session"`
Expected: FAIL — `create_cat_params` not found / `k0` is 0.5 (DEFAULT_PARAMS) not 0.42.

- [ ] **Step 3: Add CAT-params functions to the service**

Append to `backend/app/services/admin.py`:

```python
# ---- FR-ADMIN-04: CAT params ----

from app.models.admin import CatParamsVersion
from app.schemas.admin import CatParamsIn, CatParamsVersionOut


def _cat_out(v: CatParamsVersion) -> CatParamsVersionOut:
    return CatParamsVersionOut(id=v.id, version_label=v.version_label,
                               effective_date=v.effective_date, is_current=v.is_current,
                               params=v.params)


def list_cat_params(session) -> list[CatParamsVersionOut]:
    rows = session.execute(
        select(CatParamsVersion).order_by(CatParamsVersion.effective_date.desc())
    ).scalars().all()
    return [_cat_out(v) for v in rows]


def _unset_current(session) -> None:
    session.execute(
        CatParamsVersion.__table__.update().where(CatParamsVersion.c.is_current == True)
        .values(is_current=False)
    )


def create_cat_params(session, *, current, payload: CatParamsIn) -> CatParamsVersionOut:
    dup = session.execute(
        select(CatParamsVersion).where(CatParamsVersion.version_label == payload.version_label)
    ).scalar_one_or_none()
    if dup is not None:
        raise ConflictError("version_label already exists")
    if payload.set_current:
        _unset_current(session)
    v = CatParamsVersion(version_label=payload.version_label,
                        effective_date=payload.effective_date,
                        is_current=payload.set_current,
                        params=payload.params.model_dump())
    session.add(v); session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=current.user.id,
              organization_id=None, entity_type="cat_params",
              entity_id=str(v.id), details={"version_label": v.version_label,
                                            "set_current": v.is_current})
    return _cat_out(v)


def set_current_cat_params(session, *, current, version_id) -> CatParamsVersionOut:
    v = session.get(CatParamsVersion, version_id)
    if v is None:
        raise NotFound("cat params version not found")
    _unset_current(session)
    v.is_current = True
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=current.user.id,
              organization_id=None, entity_type="cat_params",
              entity_id=str(v.id), details={"set_current": True})
    return _cat_out(v)


def get_current_cat_params(session) -> CatParamsVersion | None:
    return session.execute(
        select(CatParamsVersion).where(CatParamsVersion.is_current == True)
    ).scalar_one_or_none()
```

Note the `CatParamsVersion.c.is_current` column reference — use `CatParamsVersion.__table__.c.is_current` if `.c` is not available on the mapped class. Verify by reading the model; if uncertain, use the `__table__` form in `_unset_current`:
```python
    session.execute(
        CatParamsVersion.__table__.update()
        .where(CatParamsVersion.__table__.c.is_current == True)
        .values(is_current=False)
    )
```

- [ ] **Step 4: Integrate into exam.py**

In `backend/app/services/exam.py`, find the CAT `config` dict (the line `"cat_params": dict(cat_engine.DEFAULT_PARAMS),`). Replace it with:

```python
        "cat_params": _current_cat_params_or_default(session),
```

Add the helper near the top of `exam.py` (after the imports):

```python
def _current_cat_params_or_default(session) -> dict:
    from app.services.admin import get_current_cat_params
    v = get_current_cat_params(session)
    if v is not None:
        return dict(v.params)
    return dict(cat_engine.DEFAULT_PARAMS)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_service.py tests/test_exam_service.py tests/test_exam_api.py -v`
Expected: all pass (including existing CAT tests via the DEFAULT_PARAMS fallback).

- [ ] **Step 6: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/services/admin.py backend/app/services/exam.py backend/tests/test_admin_service.py backend/tests/test_exam_service.py
git commit -m "feat(admin): CAT params versioning + exam.py snapshot (FR-ADMIN-04)"
```

---

### Task 6: Service — content quality queue (FR-ADMIN-05)

**Files:**
- Modify: `backend/app/services/admin.py` — add quality functions.
- Test: `backend/tests/test_admin_service.py` (extend).

**Interfaces:**
- Consumes: `Question`, `QuestionFeedback`, `Explanation`, `PracticeAnswer`, `ExamAnswer`, `QuestionMapping`, `not_deleted`.
- Produces: `quality_dashboard`, `list_open_feedback`, `resolve_feedback`, `list_low_accuracy_questions`, `list_missing_explanation_questions`.

**Rules (exact values):** low-accuracy = accuracy < 0.6 AND answered ≥ 5. Missing-explanation = `Question.status == published` AND no `Explanation` row. Disputed = question has ≥1 open `suspected_wrong_answer` feedback. Scope = org_admin's org questions (`Question.organization_id == scope`); system_admin = all.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_admin_service.py`. Seed questions in two orgs, feedback rows, answers. Use the existing `_question` helper pattern from `test_analytics.py` (copy a minimal version). Tests:

```python
def test_quality_dashboard_counts(db_session):
    # seed: 1 open feedback, 1 low-acc question (answered>=5, acc<0.6),
    # 1 published question with no Explanation, 1 disputed (open suspected_wrong_answer)
    ...
    out = svc.quality_dashboard(db, current=cur)
    assert out.open_feedback_count >= 1
    assert out.disputed_question_count >= 1
    assert out.low_accuracy_question_count >= 1
    assert out.missing_explanation_count >= 1


def test_resolve_feedback(db_session):
    ...seed an open feedback...
    out = svc.resolve_feedback(db, current=cur, feedback_id=fb.id,
                               payload=FeedbackResolveIn(status=QuestionFeedbackStatus.resolved))
    assert out.status == "resolved"


def test_low_accuracy_threshold_and_order(db_session):
    # a question answered 5x with 1 correct (acc 0.2) and one answered 4x (below threshold)
    ...
    rows = svc.list_low_accuracy_questions(db, current=cur, limit=10)
    assert all(r.accuracy < 0.6 and r.answered >= 5 for r in rows)
    assert rows == sorted(rows, key=lambda r: r.accuracy)


def test_quality_org_scoped(db_session):
    # feedback in o2 invisible to o1 admin
    ...
    rows = svc.list_open_feedback(db, current=cur_o1, feedback_type=None, limit=50, offset=0)
    assert all(... in o1 ...)
```
(Write concrete seed + assertions using the established fixture helpers; do not leave `...` — fill in real setup. Mirror `test_analytics.py`'s `_practice_answer`/`_question` helpers.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_service.py -v -k "quality or low_accuracy or resolve_feedback"`
Expected: FAIL — functions not found.

- [ ] **Step 3: Add the quality functions**

Append to `backend/app/services/admin.py`:

```python
# ---- FR-ADMIN-05: content quality ----

from app.models.question import (
    Explanation,
    Question,
    QuestionFeedback,
    QuestionFeedbackStatus as _QFStatus,
    QuestionFeedbackType,
    QuestionStatus,
)
from app.models.practice import PracticeAnswer
from app.models.exam import ExamAnswer
from app.schemas.admin import (
    FeedbackOut,
    FeedbackResolveIn,
    LowAccuracyQuestionOut,
    MissingExplanationQuestionOut,
    QualityDashboardOut,
)

_LOW_ACC = 0.6
_LOW_ACC_MIN_ANSWERED = 5


def _q_scope(current):
    return _admin_org_scope(current)  # None for system_admin


def _scoped_questions_q(current):
    q = select(Question).where(not_deleted(Question))
    scope = _q_scope(current)
    if scope is not None:
        q = q.where(Question.organization_id == scope)
    return q


def _answer_stats(session, current):
    """Returns {question_id: (answered, correct)} for in-scope questions."""
    sq = _scoped_questions_q(current).subquery()
    qids = session.execute(select(sq.c.id)).scalars().all()
    stats: dict[uuid.UUID, tuple[int, int]] = {}
    if not qids:
        return stats, set(qids)
    prac = session.execute(
        select(PracticeAnswer.question_id,
               func.count(),
               func.coalesce(func.sum(PracticeAnswer.is_correct.cast(Integer)), 0))
        .where(PracticeAnswer.question_id.in_(qids))
        .group_by(PracticeAnswer.question_id)
    ).all()
    exam = session.execute(
        select(ExamAnswer.question_id,
               func.count(),
               func.coalesce(func.sum(ExamAnswer.is_correct.cast(Integer)), 0))
        .where(ExamAnswer.question_id.in_(qids))
        .group_by(ExamAnswer.question_id)
    ).all()
    for qid, n, c in list(prac) + list(exam):
        a, cc = stats.get(qid, (0, 0))
        stats[qid] = (a + n, cc + int(c))
    return stats, set(qids)
```
(Add `from sqlalchemy import Integer` to the import block.)

Then the five functions:

```python
def quality_dashboard(session, *, current) -> QualityDashboardOut:
    stats, qids = _answer_stats(session, current)
    open_fb = session.execute(
        select(func.count(QuestionFeedback.id))
        .join(Question, Question.id == QuestionFeedback.question_id)
        .where(not_deleted(Question), QuestionFeedback.status == _QFStatus.open,
               *([Question.organization_id == _q_scope(current)] if _q_scope(current) is not None else []))
    ).scalar_one()
    disputed = session.execute(
        select(func.count(func.distinct(QuestionFeedback.question_id)))
        .join(Question, Question.id == QuestionFeedback.question_id)
        .where(not_deleted(Question), QuestionFeedback.status == _QFStatus.open,
               QuestionFeedback.feedback_type == QuestionFeedbackType.suspected_wrong_answer,
               *([Question.organization_id == _q_scope(current)] if _q_scope(current) is not None else []))
    ).scalar_one()
    low = sum(1 for (a, c) in stats.values()
              if a >= _LOW_ACC_MIN_ANSWERED and (c / a if a else 0.0) < _LOW_ACC)
    # published questions without an Explanation
    published_q = session.execute(
        select(Question.id).where(not_deleted(Question), Question.status == QuestionStatus.published,
               *([Question.organization_id == _q_scope(current)] if _q_scope(current) is not None else []))
    ).scalars().all()
    with_expl = set(session.execute(
        select(Explanation.question_id).where(Explanation.question_id.in_(published_q))
    ).scalars().all()) if published_q else set()
    missing = len(set(published_q) - with_expl)
    return QualityDashboardOut(open_feedback_count=open_fb, disputed_question_count=disputed,
                               low_accuracy_question_count=low, missing_explanation_count=missing)


def list_open_feedback(session, *, current, feedback_type=None, limit=50, offset=0):
    q = (select(QuestionFeedback).join(Question, Question.id == QuestionFeedback.question_id)
         .where(not_deleted(Question), QuestionFeedback.status == _QFStatus.open))
    scope = _q_scope(current)
    if scope is not None:
        q = q.where(Question.organization_id == scope)
    if feedback_type is not None:
        q = q.where(QuestionFeedback.feedback_type == feedback_type)
    total = session.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = session.execute(q.order_by(QuestionFeedback.created_at.desc())
                           .limit(limit).offset(offset)).scalars().all()
    out = [FeedbackOut(id=f.id, question_id=f.question_id, reporter_id=f.reporter_id,
                       feedback_type=f.feedback_type.value, comment=f.comment,
                       status=f.status.value, created_at=f.created_at) for f in rows]
    return out, total


def resolve_feedback(session, *, current, feedback_id, payload: FeedbackResolveIn) -> FeedbackOut:
    f = session.get(QuestionFeedback, feedback_id)
    if f is None:
        raise NotFound("feedback not found")
    # scope check via the question
    q = session.get(Question, f.question_id)
    if q is None or (not_deleted(Question).__self__ if False else False):
        raise NotFound("feedback not found")
    scope = _q_scope(current)
    if scope is not None and q.organization_id != scope:
        raise NotFound("feedback not found")
    f.status = payload.status
    session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=current.user.id,
              organization_id=q.organization_id, entity_type="feedback",
              entity_id=str(f.id), details={"status": payload.status.value})
    return FeedbackOut(id=f.id, question_id=f.question_id, reporter_id=f.reporter_id,
                       feedback_type=f.feedback_type.value, comment=f.comment,
                       status=f.status.value, created_at=f.created_at)


def list_low_accuracy_questions(session, *, current, limit=10) -> list[LowAccuracyQuestionOut]:
    stats, qids = _answer_stats(session, current)
    rows = []
    for qid, (a, c) in stats.items():
        if a >= _LOW_ACC_MIN_ANSWERED:
            acc = round(c / a, 4)
            if acc < _LOW_ACC:
                rows.append((qid, a, c, acc))
    rows.sort(key=lambda r: r[3])
    rows = rows[:limit]
    if not rows:
        return []
    stems = {q.id: q.stem for q in session.execute(
        select(Question).where(Question.id.in_([r[0] for r in rows]))).scalars().all()}
    return [LowAccuracyQuestionOut(question_id=qid, stem=stems[qid], answered=a,
                                   correct=c, accuracy=acc) for qid, a, c, acc in rows]


def list_missing_explanation_questions(session, *, current, limit=50) -> list[MissingExplanationQuestionOut]:
    q = select(Question).where(not_deleted(Question), Question.status == QuestionStatus.published)
    scope = _q_scope(current)
    if scope is not None:
        q = q.where(Question.organization_id == scope)
    pubs = session.execute(q.order_by(Question.created_at.desc()).limit(limit * 2)).scalars().all()
    if not pubs:
        return []
    with_expl = set(session.execute(
        select(Explanation.question_id).where(Explanation.question_id.in_([p.id for p in pubs]))
    ).scalars().all())
    out = [MissingExplanationQuestionOut(question_id=p.id, stem=p.stem, status=p.status.value)
           for p in pubs if p.id not in with_expl][:limit]
    return out
```

Clean up the bogus `not_deleted(Question).__self__ if False else False` line in `resolve_feedback` — remove it entirely (it was a placeholder to be deleted). The final `resolve_feedback` scope check is just the `scope` comparison.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_service.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/services/admin.py backend/tests/test_admin_service.py
git commit -m "feat(admin): content quality queue (FR-ADMIN-05)"
```

---

### Task 7: Service — audit-log viewer (FR-ADMIN-06)

**Files:**
- Modify: `backend/app/services/admin.py`
- Test: `backend/tests/test_admin_service.py` (extend).

**Interfaces:**
- Produces: `list_audit_logs(session, *, current, action=None, actor_id=None, entity_type=None, since=None, until=None, org_id=None, limit=50, offset=0) -> PaginatedAudit`.

**Rules:** org_admin sees only `organization_id == current.org_id` (and `org_id` param must equal their own or omitted). system_admin sees all; `org_id` param filters. Returns `PaginatedAudit`.

- [ ] **Step 1: Write the failing test**

```python
def test_audit_logs_org_scoped_and_filtered(db_session):
    # seed audit rows in o1 and o2, filter by action
    ...
    out = svc.list_audit_logs(db, current=cur_o1, action=None)
    assert all(i.organization_id == o1.id for i in out.items)
    out2 = svc.list_audit_logs(db, current=cur_sys, action=AuditAction.edit)
    assert all(i.action == "edit" for i in out2.items)
```
(Seed real `AuditLog` rows via `log_audit` or direct `AuditLog(...)` inserts; assert org scoping + action filter + pagination total.)

- [ ] **Step 2: Run to verify fail**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_service.py -v -k audit`
Expected: FAIL.

- [ ] **Step 3: Add the function**

Append to `backend/app/services/admin.py`:

```python
# ---- FR-ADMIN-06: audit log viewer ----

from app.models.admin import AuditLog
from app.models.enums import AuditAction as _AuditAction
from app.schemas.admin import AuditLogOut, PaginatedAudit


def list_audit_logs(session, *, current, action=None, actor_id=None, entity_type=None,
                    since=None, until=None, org_id=None, limit=50, offset=0) -> PaginatedAudit:
    scope = _admin_org_scope(current)
    if scope is not None:
        # org_admin: ignore/forbid org_id param different from own
        if org_id is not None and org_id != scope:
            raise ValidationError("cannot target another organization")
        effective_org = scope
    else:
        effective_org = org_id  # None = all orgs for system_admin
    q = select(AuditLog)
    if effective_org is not None:
        q = q.where(AuditLog.organization_id == effective_org)
    if action is not None:
        q = q.where(AuditLog.action == action)
    if actor_id is not None:
        q = q.where(AuditLog.actor_id == actor_id)
    if entity_type is not None:
        q = q.where(AuditLog.entity_type == entity_type)
    if since is not None:
        q = q.where(AuditLog.occurred_at >= since)
    if until is not None:
        q = q.where(AuditLog.occurred_at <= until)
    total = session.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = session.execute(q.order_by(AuditLog.occurred_at.desc())
                           .limit(limit).offset(offset)).scalars().all()
    items = [AuditLogOut(id=r.id, occurred_at=r.occurred_at, action=r.action.value,
                         actor_id=r.actor_id, organization_id=r.organization_id,
                         entity_type=r.entity_type, entity_id=r.entity_id,
                         details=r.details, ip_address=r.ip_address) for r in rows]
    return PaginatedAudit(items=items, total=total, limit=limit, offset=offset)
```

- [ ] **Step 4: Run tests**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_service.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/services/admin.py backend/tests/test_admin_service.py
git commit -m "feat(admin): audit log viewer (FR-ADMIN-06)"
```

---

### Task 8: Service — operational reports (FR-ADMIN-07)

**Files:**
- Modify: `backend/app/services/admin.py`
- Test: `backend/tests/test_admin_service.py` (extend).

**Interfaces:**
- Produces: `report_summary(session, *, current, org_id=None, window_days=30) -> ReportSummaryOut`.

**Rules:** `window_days` ∈ {30, 90} else `ValidationError`. Active users = distinct users with ≥1 answer in window (org-scoped via answering user's membership for org_admin; global for system_admin). Practice/exam session counts + total/correct answers in window. Published question count (in scope). Used question count = distinct questions appearing in ≥1 session in scope (window-agnostic for usage). Usage % = used/published*100. `top_error_questions` = bottom-10 by accuracy (answered ≥5, in scope). `scope` string = `"org:<id>"` or `"global"`.

- [ ] **Step 1: Write the failing test**

```python
def test_report_summary_computed_values(db_session):
    # seed: 2 users in o1, 1 in o2; practice answers (some correct) in last 30d;
    # published questions; one session using a question
    ...
    out = svc.report_summary(db, current=cur_o1, window_days=30)
    assert out.scope == f"org:{o1.id}"
    assert out.active_users >= 1
    assert out.total_answers >= 1
    assert 0.0 <= out.accuracy <= 1.0
    assert out.published_question_count >= 1
    assert out.question_bank_usage_pct >= 0.0


def test_report_summary_invalid_window(db_session):
    ...
    with pytest.raises(svc.ValidationError):
        svc.report_summary(db, current=cur, window_days=7)


def test_report_summary_org_admin_cross_org_forbidden(db_session):
    ...
    with pytest.raises(svc.ValidationError):
        svc.report_summary(db, current=cur_o1, org_id=o2.id, window_days=30)
```

- [ ] **Step 2: Run to verify fail**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_service.py -v -k report`
Expected: FAIL.

- [ ] **Step 3: Add the function**

Append to `backend/app/services/admin.py`:

```python
# ---- FR-ADMIN-07: reports ----

from app.models.practice import PracticeSession
from app.models.exam import ExamSession
from datetime import datetime, timedelta, timezone
from app.schemas.admin import ReportSummaryOut

_REPORT_WINDOWS = (30, 90)


def _scoped_user_ids(session, current):
    scope = _admin_org_scope(current)
    if scope is None:
        return None  # all users
    rows = session.execute(
        select(OrganizationMembership.user_id).where(OrganizationMembership.organization_id == scope)
    ).scalars().all()
    return set(rows)


def report_summary(session, *, current, org_id=None, window_days=30) -> ReportSummaryOut:
    if window_days not in _REPORT_WINDOWS:
        raise ValidationError("window_days must be 30 or 90")
    scope = _admin_org_scope(current)
    if scope is not None:
        if org_id is not None and org_id != scope:
            raise ValidationError("cannot target another organization")
        report_org = scope
        scope_str = f"org:{scope}"
    else:
        report_org = org_id
        scope_str = f"org:{org_id}" if org_id is not None else "global"

    user_ids = _scoped_user_ids(session, current)  # None or set
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    # answer stats in window
    def _filtered_answers(model):
        q = select(model).where(model.answered_at >= cutoff)
        if user_ids is not None:
            q = q.where(model.user_id.in_(user_ids))
        return session.execute(q).scalars().all()

    prac_ans = _filtered_answers(PracticeAnswer)
    exam_ans = _filtered_answers(ExamAnswer)
    total_answers = len(prac_ans) + len(exam_ans)
    correct_answers = sum(1 for a in prac_ans if a.is_correct) + sum(1 for a in exam_ans if a.is_correct)
    accuracy = round(correct_answers / total_answers, 4) if total_answers else 0.0
    active_users = len({a.user_id for a in list(prac_ans) + list(exam_ans)})

    # session counts in window
    def _session_count(model):
        q = select(func.count()).select_from(model).where(model.started_at >= cutoff)
        if user_ids is not None:
            q = q.where(model.user_id.in_(user_ids))
        return session.execute(q).scalar_one()
    practice_session_count = _session_count(PracticeSession)
    exam_session_count = _session_count(ExamSession)

    # question bank usage (in scope)
    qq = select(Question).where(not_deleted(Question), Question.status == QuestionStatus.published)
    if report_org is not None:
        qq = qq.where(Question.organization_id == report_org)
    published = session.execute(qq).scalars().all()
    published_question_count = len(published)
    used_qids = set()
    for model, cfgcol in ((PracticeSession, "config"), (ExamSession, "config")):
        sq = select(model)
        if user_ids is not None:
            sq = sq.where(model.user_id.in_(user_ids))
        for s in session.execute(sq).scalars().all():
            qids = (s.config or {}).get("question_ids") or []
            used_qids.update(qids)
    used_in_scope = {q.id for q in published} & used_qids
    used_question_count = len(used_in_scope)
    question_bank_usage_pct = round(used_question_count / published_question_count * 100, 2) if published_question_count else 0.0

    top_error = list_low_accuracy_questions(session, current=current, limit=10)

    return ReportSummaryOut(
        scope=scope_str, window_days=window_days, active_users=active_users,
        practice_session_count=practice_session_count, exam_session_count=exam_session_count,
        total_answers=total_answers, correct_answers=correct_answers, accuracy=accuracy,
        published_question_count=published_question_count, used_question_count=used_question_count,
        question_bank_usage_pct=question_bank_usage_pct, top_error_questions=top_error,
    )
```

- [ ] **Step 4: Run tests**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_service.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/services/admin.py backend/tests/test_admin_service.py
git commit -m "feat(admin): operational reports (FR-ADMIN-07)"
```

---

### Task 9: Router — `app/api/admin.py` + registration

**Files:**
- Create: `backend/app/api/admin.py`
- Modify: `backend/app/main.py` — register the router.
- Test: `backend/tests/test_admin_api.py` (new).

**Interfaces:**
- Consumes: all `svc.*` admin functions + `require_permission`, `CurrentUser`, `get_session`, `Session`.
- Produces: the full `/api/admin/*` route surface listed in the design doc.

- [ ] **Step 1: Write the failing API tests**

Create `backend/tests/test_admin_api.py`. Mirror `test_exam_api.py`'s auth-fixture conventions (client 3-tuple, `_headers` with role assignment + token). Tests (one representative assertion per endpoint group + 401/403):

```python
def test_users_list_200(client):
    ...
    assert r.status_code == 200

def test_users_401_without_token(client):
    c, _, _ = client
    assert c.get("/api/admin/users").status_code == 401

def test_users_403_without_perm(client):
    # individual_learner token
    assert c.get("/api/admin/users", headers=h_learner).status_code == 403

def test_class_crud(client): ...
def test_cat_params_create_and_set_current(client): ...
def test_quality_dashboard(client): ...
def test_audit_logs(client): ...
def test_report_summary_default_and_invalid_window(client): ...
def test_report_summary_org_admin_cross_org_403(client): ...
```
(Write concrete tests using the established fixtures; assert 200/401/403/422/404 as appropriate. At least one test per endpoint group; the 401 + 403 + 422 (window_days) + cross-org 403 cases are required.)

- [ ] **Step 2: Run to verify fail**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_api.py -v`
Expected: FAIL — 404 (router not registered).

- [ ] **Step 3: Write the router**

Create `backend/app/api/admin.py`:

```python
"""Admin backoffice router (FR-ADMIN-03..07). Thin delegation to app.services.admin."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser, get_current_user, require_permission
from app.db.session import get_session
from app.models.enums import AuditAction
from app.schemas.admin import (
    CatParamsIn,
    CatParamsVersionOut,
    ClassIn,
    ClassOut,
    FeedbackOut,
    FeedbackResolveIn,
    PaginatedAudit,
    QualityDashboardOut,
    ReportSummaryOut,
    UserOut,
    UserRolesIn,
    UserStatusIn,
)
from app.services import admin as svc

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _exc(e: Exception) -> HTTPException:
    if isinstance(e, svc.NotFound):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, svc.ConflictError):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, svc.ValidationError):
        return HTTPException(status_code=422, detail=str(e))
    raise e


# ---- users (FR-ADMIN-03) ----

@router.get("/users")
def list_users(
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_users")),
):
    items, total = svc.list_users(session, current=current, search=search, limit=limit, offset=offset)
    return {"items": items, "total": total}


@router.get("/users/{user_id}", response_model=UserOut)
def get_user_detail(
    user_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_users")),
):
    try:
        return svc.get_user(session, current=current, user_id=user_id)
    except svc.AdminError as e:
        raise _exc(e)
```
(Define `AdminError` as a base class in `app/services/admin.py` that `ValidationError`/`NotFound`/`ConflictError` inherit from, so the router can catch one base. Add it in Task 4's service if not already present — but since Task 9 is built after Task 4, retroactively make the three exceptions inherit `class AdminError(Exception): pass` and update `_exc` to `except svc.AdminError`. If you prefer, catch the three explicitly. Either is fine — be consistent.)

Continue with the remaining handlers: `PATCH /users/{user_id}/status` (→ `set_user_status(..., status=payload.status)`), `PUT /users/{user_id}/roles` (→ `set_user_roles(..., role_names=payload.role_names)`); the 9 class endpoints; `GET/POST /cat-params`, `PUT /cat-params/{version_id}/current`; `GET /quality/dashboard`, `GET /quality/feedback` (with `feedback_type` query), `PATCH /quality/feedback/{feedback_id}`, `GET /quality/low-accuracy`, `GET /quality/missing-explanations`; `GET /audit-logs` (with `action`/`actor_id`/`entity_type`/`since`/`until`/`org_id`/`limit`/`offset` queries); `GET /reports/summary` (with `window_days` Query default 30, `org_id` query).

Each handler: thin delegation; catch `svc.AdminError` → `_exc`; GETs do NOT commit. Mutation handlers (`PATCH`/`PUT`/`POST`/`DELETE`) call `session.commit()` after the service call succeeds (the service flushes; the router commits). Wrap mutations so a commit failure rolls back — simplest: `try: result = svc.X(...); session.commit(); return result except svc.AdminError as e: session.rollback(); raise _exc(e)`.

`window_days` on `/reports/summary`: `window_days: int = Query(30)`; the service raises `ValidationError` for non-{30,90}, mapped to 422.

Handler names: `list_users`, `get_user_detail`, `update_user_status`, `set_user_roles`, `list_classes`, `create_class`, `get_class_detail`, `update_class`, `delete_class`, `list_class_members`, `add_class_member`, `remove_class_member`, `list_cat_params`, `create_cat_params`, `set_current_cat_params`, `quality_dashboard`, `list_quality_feedback`, `resolve_quality_feedback`, `list_low_accuracy`, `list_missing_explanations`, `list_audit_logs`, `report_summary`. (None named `get_session`.)

- [ ] **Step 4: Register the router**

In `backend/app/main.py`, add `from app.api.admin import router as admin_router` (alphabetical) and `app.include_router(admin_router)`.

- [ ] **Step 5: Run tests**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_admin_api.py tests/test_admin_service.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/api/admin.py backend/app/main.py backend/tests/test_admin_api.py backend/app/services/admin.py
git commit -m "feat(admin): HTTP /api/admin/* router (FR-ADMIN-03..07)"
```
(Stage `app/services/admin.py` only if the `AdminError` base class was added here; otherwise omit it.)

---

### Task 10: Docs + final verification

**Files:**
- Modify: `CLAUDE.md`
- Modify: memory `/home/john/.claude/projects/-home-john-cissp-exam/memory/cissp-project-roadmap.md`

- [ ] **Step 1: Update CLAUDE.md**

In the "Current State" paragraph, add `**admin backoffice**` (`/api/admin/*` user/class management, CAT-param versioning, content-quality queue, audit-log viewer, operational reports; new `CatParamsVersion`/`Class`/`ClassMembership` tables; new `admin:view_reports` permission; exam.py snapshots current CAT params) to the implemented list. Update the test count. Reduce "What does NOT exist yet" to: `interactive admin UI (frontend stays at auth pages) — the full PRD backend scope is implemented; a later frontend phase will surface these APIs`. Do NOT touch other content.

- [ ] **Step 2: Update the roadmap memory**

Append an `H2` line under the sub-project status (DONE, merged), describing the admin endpoints, the three new tables, the new permission, CAT-param versioning + exam.py integration, org/global scoping, and audit-on-every-mutation. Mark `H` as DONE (H1 + H2 complete) and note that the full PRD functional backend scope is now implemented.

- [ ] **Step 3: Run the full suite + migration drift**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest -q && pytest tests/test_migrations.py -q`
Expected: all pass; record the new total; zero drift.

- [ ] **Step 4: Commit**

```bash
cd /home/john/cissp_exam
git add CLAUDE.md
git commit -m "docs: H2 admin backoffice complete (FR-ADMIN-03..07)"
```
(Commit the memory file separately via the Write tool — it lives outside the repo.)

---

## Self-Review (run after writing)

1. **Spec coverage**: FR-ADMIN-03 → Tasks 1,4,9. FR-ADMIN-04 → Tasks 1,5,9. FR-ADMIN-05 → Task 6,9. FR-ADMIN-06 → Task 7,9. FR-ADMIN-07 → Task 8,9. Seed/permission → Task 2. Models → Task 1. Schemas → Task 3. All covered.
2. **Placeholder scan**: the `...` in Task 6/8/9 test bodies are intentional "fill with concrete seeds using existing helpers" — the implementer writes real setup. The bogus `not_deleted(Question).__self__ if False else False` line in Task 6 is explicitly flagged for deletion. No other placeholders.
3. **Type consistency**: `CatParamsIn.params: CatParams`; `set_user_status(status: UserStatus)`; `set_user_roles(role_names: list[RoleName])`; `FeedbackResolveIn.status: QuestionFeedbackStatus`. `_admin_org_scope` returns `uuid.UUID | None` everywhere. Consistent.
