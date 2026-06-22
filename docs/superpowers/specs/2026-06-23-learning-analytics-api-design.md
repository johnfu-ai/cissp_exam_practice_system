# Sub-project H1: Learning Analytics API — Design

> **Status:** Design for sub-project H1 (the first half of sub-project H). Source of truth: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` §6.9 (FR-ANA). Implements the **personal learning analytics** read APIs plus the error-type classification that FR-ANA-05 requires. The admin/backoffice half (FR-ADMIN-03..07) is a separate sub-project (H2).

## Goal

Give an authenticated learner a set of read-only analytics endpoints over their own practice + exam activity: a dashboard overview, per-domain mastery, accuracy trends, weak-area identification, wrong-question error-type distribution, weekly review recommendations, and a single-call personal-report export. All aggregations are computed from existing answer/session/state tables; the only schema change is adding an `error_type` self-classification to `UserQuestionState` (FR-ANA-05).

## Scope

**In scope (FR-ANA):**
- FR-ANA-01 — dashboard overview (practiced count, accuracy, study time, streak days)
- FR-ANA-02 — 8-domain mastery (accuracy, count, avg time, mastery level)
- FR-ANA-03 — 30/90-day accuracy trend
- FR-ANA-04 — weak domains + weak knowledge points
- FR-ANA-05 — wrong-question error-type distribution (5 types) + the classification write endpoint
- FR-ANA-06 — weekly review recommendation + next-practice question set
- FR-ANA-07 — export personal learning report (JSON)

**Out of scope (deferred):**
- FR-ANA-08 (org class/student reports) — requires a class/cohort model that does not exist; belongs to a later org-management sub-project.
- Frontend UI — sub-projects B–G shipped backend APIs only; the frontend stays at auth pages. Analytics UI is a later phase.
- Caching / materialized tables — MVP computes aggregations on demand with indexed queries; NFR-PERF-01 (<2s) is met by indexed scans over per-user answer rows. A materialized dashboard table is a Phase 5 enhancement if real-world volume demands it.

## Architecture

A new bounded concern, analytics, added as a service + router pair mirroring the established pattern (sub-projects E/F):

- `backend/app/services/analytics.py` — pure business logic + DB access. Functions return Pydantic schema objects. No business logic in the router.
- `backend/app/api/analytics.py` — thin FastAPI router, `prefix="/api/analytics"`, delegates to the service.
- `backend/app/schemas/analytics.py` — response schemas.
- `backend/app/models/enums.py` — new `ErrorType` enum (FR-ANA-05's 5 types).
- `backend/app/models/practice.py` — `UserQuestionState.error_type: Mapped[ErrorType | None]` (nullable, default None).
- `backend/app/schemas/practice.py` — extend `QuestionStateIn` with `error_type`; extend the state response dict with `error_type`.
- `backend/app/services/practice.py` — `set_question_state` applies `error_type` from the payload.
- Alembic migration — `CREATE TYPE error_type`, `ALTER TABLE user_question_states ADD COLUMN error_type error_type NULL`.

**Data sources (all existing):**
- `PracticeAnswer` (user_id, question_id, is_correct, time_spent_ms, answered_at, question_snapshot, options_snapshot)
- `ExamAnswer` (user_id, question_id, is_correct, time_spent_ms, answered_at)
- `PracticeSession` / `ExamSession` (user_id, status, started_at, ended_at, correct_count, total_questions, config)
- `QuestionMapping` (question_id → domain_id, knowledge_point_id) — GLOBAL taxonomy, joinable across orgs
- `ExamDomain` (blueprint_id, number, name, weight_pct) — the 8 domains
- `UserQuestionState` (user_id, question_id, mastery_level, is_flagged_review, + new error_type)

**Unified answer view:** analytics must aggregate across both practice and exam answers. Rather than a SQL UNION view (which complicates the ORM), the service runs two grouped queries (practice + exam) per domain and merges the (correct, answered, time) buckets in Python. This keeps each query a simple indexed scan and avoids a DB-level view migration. The merge is a small helper.

**Tenant & ownership scoping:** every query filters `user_id == current.user.id`. Answers are NOT organization-scoped in the analytics path (a user's own activity is theirs regardless of org), but the domain/knowledge-point taxonomy reads are GLOBAL. The classification write endpoint (`set_question_state`) keeps its existing `organization_id` guard on the question.

**Permission gating:** analytics endpoints are gated by `practice:read` (which `individual_learner`, `instructor`, `org_admin`, `system_admin` all hold). Introducing a dedicated `analytics:read` permission would require a seed/migration change to the role-permission matrix; YAGNI — `practice:read` already means "may view own practice data," which is exactly what analytics is. (H2 may revisit if admin-overview analytics need a distinct gate.)

**Service-layer rules (carry forward):** caller commits after mutations; `log_audit` flushes only. Analytics endpoints are read-only (no commits). The one mutation (error-type classification) reuses the existing `set_question_state` path, which the route already commits.

## Components

### 1. `ErrorType` enum (`app/models/enums.py`)

```python
class ErrorType(str, enum.Enum):
    concept_unclear = "concept_unclear"      # 概念不清
    misread_stem = "misread_stem"            # 审题错误
    memory_lapse = "memory_lapse"            # 记忆错误
    option_confusion = "option_confusion"    # 选项混淆
    time_pressure = "time_pressure"          # 时间压力
```

### 2. Model + migration

`UserQuestionState.error_type: Mapped[ErrorType | None] = mapped_column(Enum(ErrorType, name="error_type", create_type=True), nullable=True)` (no server default → NULL).

Migration: `CREATE TYPE error_type` (values above), `ALTER TABLE user_question_states ADD COLUMN error_type error_type`; downgrade `DROP COLUMN` + `DROP TYPE error_type`. No data backfill (NULL = unclassified).

### 3. Schemas (`app/schemas/analytics.py`)

```python
class DashboardOut(BaseModel):
    practiced_questions: int            # distinct question_id across practice+exam answers
    total_answered: int                 # all answer rows (is_correct not None)
    correct_count: int
    accuracy: float                     # correct/total_answered (0.0 if none), 4dp
    study_time_ms: int                  # sum(time_spent_ms) across answers
    streak_days: int                    # consecutive days with >=1 answer ending today (UTC date)
    last_active_at: datetime | None

class DomainMasteryOut(BaseModel):
    domain_id: uuid.UUID
    number: int
    name: str
    weight_pct: int
    answered: int
    correct: int
    accuracy: float
    avg_time_ms: int                    # 0 if none
    mastery_level: str                  # MasteryLevel value derived from accuracy

class TrendPoint(BaseModel):
    date: date                          # answered_at date (UTC)
    answered: int
    correct: int
    accuracy: float

class TrendOut(BaseModel):
    window_days: int                    # 30 or 90
    points: list[TrendPoint]            # one per day with activity, sorted asc

class WeakAreaOut(BaseModel):
    domain_id: uuid.UUID | None
    knowledge_point_id: uuid.UUID | None
    label: str                          # domain name or KP name
    answered: int
    correct: int
    accuracy: float

class WeakAreasOut(BaseModel):
    weak_domains: list[WeakAreaOut]     # accuracy < 0.6 and answered >= 3, sorted accuracy asc, top 8
    weak_knowledge_points: list[WeakAreaOut]  # same threshold, top 10

class ErrorTypeBreakdown(BaseModel):
    error_type: str | None              # None = unclassified
    count: int

class ErrorTypeOut(BaseModel):
    total_wrong_classified: int
    distribution: list[ErrorTypeBreakdown]   # 5 types + an "unclassified" bucket

class ReviewRecommendationOut(BaseModel):
    focus_domain: WeakAreaOut | None            # weakest domain this week
    wrong_to_review: list[uuid.UUID]            # question_ids wrong, not mastered, not flagged-resolved
    next_practice_question_ids: list[uuid.UUID]  # <=10 from weak areas, least-recently-practiced
    rationale: str

class PersonalReportOut(BaseModel):
    generated_at: datetime
    dashboard: DashboardOut
    domains: list[DomainMasteryOut]
    trend_30d: TrendOut
    weak_areas: WeakAreasOut
    error_types: ErrorTypeOut
    recommendation: ReviewRecommendationOut
```

`QuestionStateIn` (extend, additive): `error_type: ErrorType | None = None`. The state response dict gains `"error_type": state.error_type.value if state.error_type else None`.

### 4. Service (`app/services/analytics.py`)

Public functions (each takes `session, *, user_id` and returns the matching schema):
- `dashboard(session, *, user_id) -> DashboardOut`
- `domain_mastery(session, *, user_id, blueprint) -> list[DomainMasteryOut]` — uses the current blueprint's 8 domains.
- `trend(session, *, user_id, window_days) -> TrendOut`
- `weak_areas(session, *, user_id) -> WeakAreasOut`
- `error_type_breakdown(session, *, user_id) -> ErrorTypeOut`
- `recommendation(session, *, user_id, blueprint) -> ReviewRecommendationOut`
- `personal_report(session, *, user_id, blueprint) -> PersonalReportOut` — composes the above.

Internal helpers:
- `_answer_buckets(session, user_id, since=None) -> dict[domain_id, {answered, correct, time_ms}]` — runs the practice + exam grouped queries and merges. Optionally filtered by `since` (for trend).
- `_mastery_from_accuracy(acc: float) -> MasteryLevel` — `>=0.8 mastered`, `>=0.6 reviewing`, `>=0.4 learning`, else `not_started` (matches the existing `MasteryLevel` semantics already used by `UserQuestionState`).
- `_streak(dates: set[date]) -> int` — consecutive-day count ending today.

Blueprint lookup: the router resolves the current blueprint once (reuse `exam._current_blueprint` semantics — but to avoid a cross-service import, analytics has its own `_current_blueprint(session)` helper, or imports `from app.services.exam import _current_blueprint`). Decision: add a small local `_current_blueprint(session)` to avoid coupling to a private name in another service. If no current blueprint exists, domain-mastery/recommendation endpoints return empty/None gracefully (200 with empty lists), not 422 — analytics should degrade gracefully when taxonomy isn't seeded.

### 5. Router (`app/api/analytics.py`)

```
GET /api/analytics/dashboard                 -> DashboardOut          (practice:read)
GET /api/analytics/domains                   -> list[DomainMasteryOut] (practice:read)
GET /api/analytics/trend?window_days=30|90   -> TrendOut              (practice:read)
GET /api/analytics/weak-areas                -> WeakAreasOut          (practice:read)
GET /api/analytics/error-types               -> ErrorTypeOut          (practice:read)
GET /api/analytics/recommendation            -> ReviewRecommendationOut (practice:read)
GET /api/analytics/report                    -> PersonalReportOut     (practice:read)
```

`window_days` query param: int, must be 30 or 90; default 30; 422 otherwise. Registered in `app/main.py` alongside the other routers.

The error-type classification is exposed through the **existing** `PUT /api/practice/questions/{question_id}/state` (extended `QuestionStateIn`), not a new analytics route — classification is a per-question study action, so it lives with the rest of question-state.

## Data flow

1. Learner answers questions (practice/exam) — already recorded by sub-projects E/F.
2. Learner optionally classifies a wrong question: `PUT /api/practice/questions/{id}/state` with `{"error_type": "concept_unclear"}` → `set_question_state` writes `UserQuestionState.error_type`.
3. Learner opens analytics: each `GET /api/analytics/*` runs indexed per-user aggregations and returns the schema. `/report` composes all.

## Error handling

- All analytics GETs are personal-scoped; a request with no answers returns zero/empty structures (200), never 404 — a new user has a valid empty dashboard.
- `window_days` other than 30/90 → 422 (Pydantic validator or explicit check).
- No current blueprint → domain-mastery returns `[]`, recommendation returns `focus_domain=None` + empty lists, 200.
- Classification write: 404 if the question doesn't exist / is deleted / wrong org (existing `set_question_state` behavior, unchanged); 422 if `error_type` is not a valid enum value (Pydantic).

## Testing

`backend/tests/test_analytics.py` against the real `cissp_test` DB (SAVEPOINT rollback, `Base.metadata.create_all`). Fixtures seed a user, a current blueprint with 8 domains, knowledge points, and questions mapped to domains/KPs; then seed `PracticeAnswer`/`ExamAnswer`/`UserQuestionState` rows and assert each endpoint's computed values:
- dashboard counts/accuracy/streak (incl. 0-answer user, multi-day streak, gap-breaking streak)
- domain mastery merge of practice+exam answers, mastery-level thresholds
- trend 30/90 windows, daily bucketing, accuracy
- weak-areas threshold (accuracy < 0.6, answered >= 3) and ordering
- error-type distribution (5 types + unclassified)
- recommendation: focus domain = weakest, wrong-to-review excludes mastered, next-practice excludes recently-practiced, <=10
- report composes all sub-objects
- classification: `PUT /api/practice/questions/{id}/state` with `error_type` persists and returns it; invalid enum → 422; other-user question → 404.

`backend/tests/test_migrations.py` — the no-autogenerate-drift test must remain clean after adding the `error_type` column + enum (run `alembic revision --autogenerate`, filter the hand-written `uq_users_email_lower` index as usual). A new migration file is produced and committed.

## Acceptance

- FR-ANA-01..07 each covered by ≥1 test and a working endpoint.
- 272 existing tests still pass; migration drift test passes.
- No business logic in route handlers; service owns queries.
- Personal scoping enforced (cross-user data never appears).
- Analytics degrades gracefully for empty/new users and missing blueprint.
