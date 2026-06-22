# Sub-project H2: Admin Backoffice API — Design

> **Status:** Design for sub-project H2 (the second half of sub-project H). Source of truth: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` §6.10 (FR-ADMIN). Implements the admin backoffice read/write APIs for FR-ADMIN-03..07. FR-ADMIN-01 (question bank management) was delivered in sub-project C; FR-ADMIN-02 (taxonomy management) in sub-project D. H2 completes the admin surface and, with it, the full PRD functional scope.

## Goal

Give administrators (org_admin, system_admin) and content editors a set of backoffice endpoints: user/role/class management (FR-ADMIN-03), CAT-parameter versioning wired into exam creation (FR-ADMIN-04), a content-quality triage queue (FR-ADMIN-05), an audit-log viewer (FR-ADMIN-06), and org/global operational reports (FR-ADMIN-07). Backend-only, consistent with sub-projects B–G (the frontend stays at auth pages).

## Scope

**In scope (FR-ADMIN):**
- FR-ADMIN-03 — user management: list/get users, enable/disable (status), assign roles within an org; class (班级/学习组) model + CRUD + membership.
- FR-ADMIN-04 — exam config: versioned CAT parameters (`CatParamsVersion`) with set-current; the exam service snapshots the current version into new CAT sessions (historical integrity). Blueprint/domain editing (题量/时长/组卷策略) is already delivered in sub-project D — not rebuilt.
- FR-ADMIN-05 — content quality: open-correction-feedback queue + resolve/wont-fix transitions, low-accuracy-question list, missing-explanation-question list.
- FR-ADMIN-06 — audit log: filtered, paginated viewer over `AuditLog` (login/import/edit/publish/delete/permission_change/config_change/archive).
- FR-ADMIN-07 — reports: active users, practice volume, accuracy, question-bank usage, question error rate (org-scoped for org_admin, global for system_admin).

**Out of scope (deferred):**
- Frontend admin UI (backend-only phase, like B–G).
- Cohort/class-roster analytics (FR-ANA-08) — a later org-management sub-project; the Class model added here unblocks it but the analytics are not built.
- Admin-initiated password reset / email verification flows — later auth hardening.
- Bulk user import, SSO provisioning.
- Real-time / streaming reports; async report generation (Celery/RQ) — the PRD names these for later phases; MVP computes synchronously with indexed scans.

## Architecture

A new bounded concern, admin, added as a service + router pair mirroring the established pattern (sub-projects D/E/F/G/H1):

- `backend/app/services/admin.py` — pure business logic + DB access; functions return Pydantic schemas. Owns all org/global scoping decisions.
- `backend/app/api/admin.py` — thin FastAPI router, `prefix="/api/admin"`, delegates to the service.
- `backend/app/schemas/admin.py` — request/response schemas.
- `backend/app/models/admin.py` — gains `CatParamsVersion` (exam-config data, GLOBAL like the rest of taxonomy).
- `backend/app/models/auth.py` — gains `Class` + `ClassMembership` (org-scoped content).
- `backend/app/services/exam.py` — one-line change: CAT session creation snapshots the current `CatParamsVersion` instead of `cat_engine.DEFAULT_PARAMS` (with fallback).
- `backend/app/db/seed.py` — add `admin:view_reports` permission to the matrix (org_admin + system_admin); bump `seed_version`.
- Alembic migration — three new tables (`cat_params_versions`, `classes`, `class_memberships`).

**Data sources (all existing):** `User`, `Role`, `Permission`, `RolePermission`, `OrganizationMembership`, `Organization`, `AuditLog`, `Question`, `QuestionFeedback`, `Explanation`, `PracticeSession`, `ExamSession`, `PracticeAnswer`, `ExamAnswer`, `QuestionMapping`, `ExamBlueprint`, `ExamDomain`. Plus the three new tables.

**Admin scoping (the central rule):** every admin service function takes `current: CurrentUser` and applies `_admin_org_scope(current)`:
- `system_admin` → `None` (no org filter; sees global). May optionally filter by an `org_id` query param.
- `org_admin` → `current.org_id` (every query restricted to that org). An org_admin cannot read or mutate another org's users, classes, feedback, audit logs, or report data.

Content editors (`content_editor`) hold `question:publish` and triage the quality queue, but do NOT get `admin:manage_users` / `admin:view_audit` / `admin:view_reports` — they see only the quality endpoints, scoped to their org's questions.

**Permission gating:**
| Endpoint group | Permission | Held by |
|---|---|---|
| Users + classes (FR-ADMIN-03) | `admin:manage_users` | instructor, org_admin, system_admin |
| CAT params (FR-ADMIN-04) | `admin:manage_taxonomy` | org_admin, system_admin |
| Quality queue (FR-ADMIN-05) | `question:publish` | content_editor, org_admin, system_admin |
| Audit viewer (FR-ADMIN-06) | `admin:view_audit` | org_admin, system_admin |
| Reports (FR-ADMIN-07) | `admin:view_reports` (new) | org_admin, system_admin |

`admin:view_reports` is a new permission code added to the seed matrix (data change, not a schema migration). This is the only new permission in H2.

**Service-layer rules (carry forward):** caller commits after mutations; `log_audit` flushes only (does not commit); read-only GETs do NOT commit. Mutations in admin (role changes, class CRUD, CAT-params set-current, feedback resolution, user status changes) are audited via `log_audit` with the matching `AuditAction` (permission_change / config_change / edit / archive).

## Components

### 1. New models

**`CatParamsVersion`** (in `app/models/admin.py`, GLOBAL — exam config is data):

```python
class CatParamsVersion(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "cat_params_versions"
    version_label: Mapped[str] = mapped_column(String(50), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # params shape: {"k0": float, "decay": float, "base_se": float, "early_stop_enabled": bool}
```

Only one row may have `is_current = True` at a time. Enforced in the service (`set_current` unsets siblings in the same transaction); a partial unique index `WHERE is_current` is NOT added (the service-level invariant plus tests suffice and keep the migration simple — matches the seed's `is_current` handling for `ExamBlueprint`).

**`Class`** (in `app/models/auth.py`, org-scoped content, soft-deletable):

```python
class Class(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "classes"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    instructor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
```

**`ClassMembership`** (in `app/models/auth.py`):

```python
class ClassMembership(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "class_memberships"
    __table_args__ = (UniqueConstraint("class_id", "user_id", name="uq_class_membership"),)
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
```

### 2. Migration

One Alembic revision (`down_revision` = current head). Creates the three tables with their FKs/unique constraints. `CatParamsVersion.params` is JSONB (no native ENUM involved). `Class` carries `organization_id` (NOT NULL, FK) + `deleted_at` (nullable) from its mixins. `ClassMembership` has the `(class_id, user_id)` unique constraint. Downgrade drops the three tables in reverse. No ENUM types are added or removed, so no `CREATE/DROP TYPE` is needed.

### 3. Seed change

`PERMISSIONS` gains `("admin:view_reports", "View operational reports")`. `ROLE_PERMISSIONS` adds `"admin:view_reports"` to `org_admin` and `system_admin`. `SEED_VERSION` bumped (so re-seed applies the new permission + matrix rows idempotently). No new role.

### 4. Schemas (`app/schemas/admin.py`)

```python
class UserOut(BaseModel):
    id: uuid.UUID; email: str; display_name: str | None; status: str
    default_organization_id: uuid.UUID | None; roles: list[str]  # role names in the caller's org

class UserStatusIn(BaseModel):
    status: UserStatus  # active | disabled

class UserRolesIn(BaseModel):
    role_names: list[RoleName]  # replaces the user's roles in the caller's org

class ClassOut(BaseModel):
    id: uuid.UUID; name: str; description: str | None
    instructor_id: uuid.UUID | None; organization_id: uuid.UUID
    member_count: int

class ClassIn(BaseModel):
    name: str; description: str | None = None; instructor_id: uuid.UUID | None = None

class ClassMemberOut(BaseModel):
    user_id: uuid.UUID; email: str; display_name: str | None

class CatParamsVersionOut(BaseModel):
    id: uuid.UUID; version_label: str; effective_date: date
    is_current: bool; params: dict

class CatParamsIn(BaseModel):
    version_label: str; effective_date: date
    params: CatParams  # validated sub-schema: k0>0, decay>=0, base_se>0, early_stop_enabled: bool
    set_current: bool = True

class FeedbackOut(BaseModel):
    id: uuid.UUID; question_id: uuid.UUID; reporter_id: uuid.UUID | None
    feedback_type: str; comment: str | None; status: str; created_at: datetime

class FeedbackResolveIn(BaseModel):
    status: QuestionFeedbackStatus  # resolved | wont_fix
    comment: str | None = None

class QualityDashboardOut(BaseModel):
    open_feedback_count: int
    low_accuracy_question_count: int        # accuracy < 0.6, answered >= 5, in scope
    missing_explanation_count: int          # published questions with no Explanation row, in scope
    disputed_question_count: int            # questions with >=1 open suspected_wrong_answer feedback

class LowAccuracyQuestionOut(BaseModel):
    question_id: uuid.UUID; stem: str; answered: int; correct: int; accuracy: float

class MissingExplanationQuestionOut(BaseModel):
    question_id: uuid.UUID; stem: str; status: str

class AuditLogOut(BaseModel):
    id: uuid.UUID; occurred_at: datetime; action: str
    actor_id: uuid.UUID | None; organization_id: uuid.UUID | None
    entity_type: str | None; entity_id: str | None; details: dict | None; ip_address: str | None

class PaginatedAudit(BaseModel):
    items: list[AuditLogOut]; total: int; limit: int; offset: int

class ReportSummaryOut(BaseModel):
    scope: str                               # "org:<id>" or "global"
    window_days: int                         # 30
    active_users: int                        # distinct users with >=1 answer in window
    practice_session_count: int
    exam_session_count: int
    total_answers: int
    correct_answers: int
    accuracy: float                          # correct/total, 0.0 if none, 4dp
    published_question_count: int
    used_question_count: int                 # distinct questions appearing in >=1 session in scope
    question_bank_usage_pct: float           # used/published * 100, 0.0 if none
    top_error_questions: list[LowAccuracyQuestionOut]  # bottom-10 by accuracy (answered>=5)
```

`CatParams` sub-schema validates the param shape and ranges (rejects non-positive `k0`/`base_se`, negative `decay`).

### 5. Service (`app/services/admin.py`)

Public functions (signatures):
- **Users (FR-ADMIN-03):** `list_users(session, *, current, search=None, limit, offset) -> tuple[list[UserOut], total]`; `get_user(session, *, current, user_id) -> UserOut`; `set_user_status(session, *, current, user_id, status) -> UserOut` (audits `permission_change`); `set_user_roles(session, *, current, user_id, role_names) -> UserOut` (audits `permission_change`). Role assignment operates on `OrganizationMembership` rows for `current.org_id` (org_admin) or the user's default org (system_admin) — never destroys memberships in other orgs.
- **Classes (FR-ADMIN-03):** `list_classes`, `create_class`, `get_class`, `update_class`, `delete_class` (soft delete), `list_class_members`, `add_class_member`, `remove_class_member`. All org-scoped via `_admin_org_scope`.
- **CAT params (FR-ADMIN-04):** `list_cat_params(session) -> list[CatParamsVersionOut]`; `create_cat_params(session, *, current, payload) -> CatParamsVersionOut` (if `set_current`, unsets siblings — audited `config_change`); `set_current_cat_params(session, *, current, version_id) -> CatParamsVersionOut` (audits `config_change`); `get_current_cat_params(session) -> CatParamsVersion | None` (read helper, no permission gate — used by exam.py).
- **Quality (FR-ADMIN-05):** `quality_dashboard(session, *, current) -> QualityDashboardOut`; `list_open_feedback(session, *, current, feedback_type=None, limit, offset) -> ...`; `resolve_feedback(session, *, current, feedback_id, payload) -> FeedbackOut` (audits `edit`); `list_low_accuracy_questions(session, *, current, limit) -> list[LowAccuracyQuestionOut]`; `list_missing_explanation_questions(session, *, current, limit) -> list[MissingExplanationQuestionOut]`.
- **Audit (FR-ADMIN-06):** `list_audit_logs(session, *, current, action=None, actor_id=None, entity_type=None, since=None, until=None, limit, offset) -> PaginatedAudit`. Org-scoped for org_admin (filters `organization_id == org_id`); global for system_admin.
- **Reports (FR-ADMIN-07):** `report_summary(session, *, current, org_id=None, window_days=30) -> ReportSummaryOut`. `window_days` accepts `{30, 90}` only, default 30, 422 otherwise — matches the analytics trend contract for a consistent API.

Internal helpers:
- `_admin_org_scope(current) -> uuid.UUID | None` — None for system_admin, `current.org_id` for everyone else.
- `_scoped_users_query(session, current)` / `_scoped_questions_query(session, current)` / `_scoped_answers_query(session, current)` — shared scoping query builders. Answers are scoped via the answering user's membership in the admin's org (for org_admin) or unscoped (system_admin).
- `ValidationError` / `NotFound` / `ConflictError` exceptions, mapped in the router to 422 / 404 / 409 (mirrors taxonomy_admin / practice / exam services).

### 6. exam.py integration (FR-ADMIN-04)

In `app/services/exam.py` CAT session creation, replace:
```python
"cat_params": dict(cat_engine.DEFAULT_PARAMS),
```
with:
```python
"cat_params": _current_cat_params_or_default(session),
```
where the helper returns `dict(current_version.params)` if a current `CatParamsVersion` exists, else `dict(cat_engine.DEFAULT_PARAMS)`. The params are snapshotted into `ExamSession.config` at creation time — so later edits to `CatParamsVersion` never change existing sessions (NFR-DATA-01-style historical integrity). Existing CAT tests keep passing because the fallback equals `DEFAULT_PARAMS` when no version is seeded.

### 7. Router (`app/api/admin.py`)

```
GET    /api/admin/users                              -> list (admin:manage_users)
GET    /api/admin/users/{user_id}                    -> UserOut (admin:manage_users)
PATCH  /api/admin/users/{user_id}/status             -> UserOut (admin:manage_users)
PUT    /api/admin/users/{user_id}/roles              -> UserOut (admin:manage_users)

GET    /api/admin/classes                            -> list (admin:manage_users)
POST   /api/admin/classes                            -> ClassOut (admin:manage_users)
GET    /api/admin/classes/{class_id}                 -> ClassOut (admin:manage_users)
PATCH  /api/admin/classes/{class_id}                 -> ClassOut (admin:manage_users)
DELETE /api/admin/classes/{class_id}                 -> 204 (admin:manage_users)
GET    /api/admin/classes/{class_id}/members         -> list (admin:manage_users)
POST   /api/admin/classes/{class_id}/members         -> 204 (admin:manage_users)
DELETE /api/admin/classes/{class_id}/members/{user_id} -> 204 (admin:manage_users)

GET    /api/admin/cat-params                         -> list (admin:manage_taxonomy)
POST   /api/admin/cat-params                         -> CatParamsVersionOut (admin:manage_taxonomy)
PUT    /api/admin/cat-params/{version_id}/current    -> CatParamsVersionOut (admin:manage_taxonomy)

GET    /api/admin/quality/dashboard                  -> QualityDashboardOut (question:publish)
GET    /api/admin/quality/feedback                   -> list (question:publish)
PATCH  /api/admin/quality/feedback/{feedback_id}     -> FeedbackOut (question:publish)
GET    /api/admin/quality/low-accuracy               -> list (question:publish)
GET    /api/admin/quality/missing-explanations       -> list (question:publish)

GET    /api/admin/audit-logs                         -> PaginatedAudit (admin:view_audit)

GET    /api/admin/reports/summary                    -> ReportSummaryOut (admin:view_reports)
```

`window_days` query param on `/reports/summary` (default 30, must be 30 or 90, else 422). `org_id` query param on `/reports/summary` and `/audit-logs` (system_admin only; org_admin's own org is implied and supplying another org's id → 403). Registered in `app/main.py`. Handler names avoid `get_session`.

## Data flow

1. system_admin seeds a `CatParamsVersion` (set_current) → new CAT sessions snapshot its params.
2. org_admin creates classes, adds members, assigns roles; each mutation writes an `AuditLog`.
3. Learners submit `QuestionFeedback`; content_editor triages via `/quality/feedback`, resolving or wont-fixing.
4. org_admin / system_admin opens `/audit-logs` to review administrative actions, `/reports/summary` for operational health.
5. All reads are org-scoped (org_admin) or global (system_admin); cross-org data never surfaces.

## Error handling

- 401 without a token; 403 with a token lacking the required permission (handled by `require_permission`).
- org_admin supplying another org's `org_id` → 403 (checked in service).
- 404 when the target user/class/feedback/cat-params version doesn't exist or is outside the caller's scope (treat out-of-scope as 404, not 403, to avoid leaking existence).
- 422 for invalid enum values (Pydantic), invalid `CatParams` ranges, or `window_days` ∉ {30, 90}.
- 409 on `set_current` races / duplicate `(class_id, user_id)` membership / duplicate `version_label`.
- Empty results return 200 with empty lists / zero counts — never 404.

## Testing

`backend/tests/test_admin_service.py` + `backend/tests/test_admin_api.py` against the real `cissp_test` DB (SAVEPOINT rollback, `Base.metadata.create_all`). Fixtures seed users in two orgs, roles, classes, feedback, audit rows, answers. Assert:
- **FR-ADMIN-03:** list/get/update-status/set-roles; org_admin cannot touch another org's user (404); class CRUD + membership + soft delete; role assignment only affects the caller's org membership.
- **FR-ADMIN-04:** create CatParamsVersion → is_current flips, siblings unset; exam CAT session snapshots the current version's params; fallback to DEFAULT_PARAMS when none; set_current; invalid params → 422.
- **FR-ADMIN-05:** quality dashboard counts; open-feedback list + filter; resolve/wont_fix transitions; low-accuracy threshold (accuracy<0.6, answered≥5) and ordering; missing-explanation list (published questions lacking an Explanation); org scoping (other org's feedback invisible).
- **FR-ADMIN-06:** audit list filters (action, actor, entity_type, date range) + pagination; org_admin sees only their org's logs; system_admin sees all.
- **FR-ADMIN-07:** report summary computed values (active users, volumes, accuracy, usage %, top error questions); org-scoped vs global; window_days 30/90 default 30 else 422.
- API tests: 401 without token; 403 with insufficient role; correct permission per endpoint group.
- `tests/test_migrations.py` — no-autogenerate-drift stays clean (run `alembic revision --autogenerate`, filter `uq_users_email_lower`).
- `tests/test_seed.py` — the new `admin:view_reports` permission + matrix rows are seeded; re-seed is idempotent.

## Acceptance

- FR-ADMIN-03..07 each covered by ≥1 test and a working endpoint.
- 306 existing tests still pass; migration drift test passes; seed test passes.
- No business logic in route handlers; service owns queries and scoping.
- org_admin is strictly org-scoped (cross-org data never appears); system_admin is global.
- Every mutation writes an `AuditLog`.
- CAT params are versioned and snapshotted into sessions (historical integrity); existing CAT behavior unchanged when no version exists.
