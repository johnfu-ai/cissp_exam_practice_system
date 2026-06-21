# Foundations & Data Model — Design Spec

- **Sub-project:** A (of the CISSP Exam Practice System decomposition)
- **Date:** 2026-06-21
- **Status:** Draft — pending user review
- **Source PRD:** `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md`
- **Terminal state of this spec:** an implementation plan (via the writing-plans skill), not code.

## 1. Context & Scope

The CISSP Exam Practice System PRD describes a full multi-tenant SaaS platform (auth + RBAC, question bank, import pipeline, practice, fixed exams, a CAT engine, analytics, admin backend). It is too large for one design spec and one implementation plan. The work has been decomposed into sub-projects, each with its own spec → plan → implementation cycle:

| Sub-project | Maps to PRD | Delivers |
|---|---|---|
| **A. Foundations & data model** *(this spec)* | Phase 0 + §9.4 | Scaffolding, all core models, seeded reference data, migrations, tests |
| B. Auth & users | FR-USER | Registration, login, JWT, RBAC, personal/org isolation |
| C. Question bank + import | FR-IMP, FR-Q, FR-TAX | Import pipeline, question lifecycle, dedup, admin management |
| D. Practice & answers | FR-PRAC, FR-ANS | Practice sessions, answer flow, explanations, bookmarks, notes, wrong-question book |
| E. Fixed mock exam | FR-EXAM | Fixed-length exam, domain-weight assembly, timer, report |
| F. Basic CAT mock exam | FR-CAT, §11 | Rule-driven CAT (MVP strategy, not 3PL IRT), forward-only, readiness report |
| G. Learning analytics | FR-ANA | Dashboard, per-domain breakdown, weak areas, trends |
| H. Admin backend polish | FR-ADMIN, NFR | Content quality, audit viewer, exam config, reports |

Dependency order: A blocks everything. B and C depend on A and are independent of each other. D depends on C. E and F depend on D. G depends on D/E/F. H is cross-cutting, late.

**This spec covers only sub-project A.**

### Decisions locked during brainstorming

1. **First sub-project = A** (Foundations & data model). It is the true prerequisite for every later sub-project.
2. **Tenancy = model + scope all content tables now.** `Organization`, `Role`, `Permission` models are created in A, and every *content* table carries a NOT NULL `organization_id` from day one. System-reference taxonomy tables (`ExamBlueprint`, `ExamDomain`, `KnowledgePoint`, `Tag`) are global by design and deliberately excluded from tenant scoping (see §3.2). Satisfies PRD §15's warning that deferring tenant/role/audit design causes expensive late refactors.
3. **Scope of A = models + scaffolding + seeded data only.** FastAPI boots, DB migrates, reference data seeds, a health-check endpoint exists, model/migration tests pass. No auth flows, no business endpoints — those land in B/C.
4. **Model structure = domain-grouped subpackages on one SQLAlchemy 2.x `Base`, with reusable mixins** encoding the PRD's cross-cutting rules (timestamps, soft-delete, tenant scoping, audit subject) as code rather than per-table convention.

## 2. Architecture & Scaffolding

### 2.1 Repo layout

Single git repository, monorepo (consistent with `CLAUDE.md`):

```
cissp_exam/
├── backend/                 # FastAPI
│   ├── app/
│   │   ├── main.py          # FastAPI app factory + /health route
│   │   ├── core/            # config (pydantic-settings), logging, db engine/session
│   │   ├── models/          # domain-grouped subpackages (see §3)
│   │   ├── db/              # base.py (Base + mixins), session.py, seed.py
│   │   └── alembic/         # migrations + alembic.ini
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # Next.js (App Router, TS, Tailwind)
│   ├── src/app/             # minimal bootable app + health placeholder
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml       # postgres, redis, backend, frontend
├── docs/                    # PRD + specs (specs under docs/superpowers/specs/)
└── CLAUDE.md
```

### 2.2 Stack & pinned versions

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic, psycopg (Postgres driver), pydantic-settings, redis client, pytest.
- **Frontend:** Node 20 LTS, Next.js (App Router), TypeScript, Tailwind CSS.
- **Infra (dev via Docker Compose):** PostgreSQL 16, Redis 7, backend (uvicorn `--reload`), frontend (`next dev`).

### 2.3 Tooling defaults (stated explicitly)

- Python packaging via `pip` + `venv` + `requirements.txt` (per `CLAUDE.md`; not uv/Poetry). Frontend via `npm`.
- Configuration via `.env` + pydantic-settings `Settings` class: DB URL, Redis URL, env name, JWT placeholder settings (present but unused until B).
- **No background worker in A.** Celery/RQ/Arq is deferred to sub-project C, where async import jobs first appear.
- **No Pydantic business schema layer in A** beyond what the health route needs. The full `schemas/` package arrives with B/C.

### 2.4 Frontend posture in A

Deliberately thin: a bootable Next.js app with one placeholder page (a "system online" status that hits the backend `/health` endpoint) so the full stack comes up green end-to-end. Real UI is B onward.

## 3. Data Model

### 3.1 Shared Base & mixins (`backend/app/db/base.py`)

One SQLAlchemy 2.x `DeclarativeBase` for the whole app. Four mixins encode the PRD's cross-cutting rules as code:

- **`TimestampMixin`** — `created_at`, `updated_at` (timezone-aware UTC, server-default `now()`, auto-update on save). Every table.
- **`SoftDeleteMixin`** — `deleted_at` nullable. Default query scope excludes soft-deleted rows via a shared query helper / base query class that sub-projects use for all reads (filters `deleted_at IS NULL`); a `with_deleted()` escape hatch exists for admin views. Per NFR-DATA-02.
- **`TenantScopedMixin`** — `organization_id` FK→`organizations.id`, **NOT NULL**. Every content table is tenant-scoped from day one. No nullable-deferred scoping.
- **`AuditSubjectMixin`** — `created_by_id`, `updated_by_id`, `reviewed_by_id` (FK→`users.id`, nullable). For question lifecycle and admin-managed tables per FR-Q-06.

**Primary keys:** UUID (`UUID` type, `server_default=gen_random_uuid()`) on every table — avoids integer-ID enumeration and is friendlier for distributed/sync later.

**Enumerations:** native Postgres `ENUM` types for fixed vocabularies (question status, role names, session status, import status, etc.), not magic strings.

### 3.2 Models by bounded context

Each context is a subpackage under `backend/app/models/`. A `models/__init__.py` registry imports them all so Alembic autogenerate sees every table.

#### `auth/` (tables only in A; endpoints in B)
- **`Organization`** — tenant. `name`, `slug` (unique), `kind` (enum: `personal`/`institution`), `status`. Timestamps. One built-in `personal` org seeded.
- **`User`** — `email` (unique, case-insensitive via functional index on `lower(email)`), `password_hash` (column only; hashing *logic* is B), `display_name`, `status` (active/disabled), `default_organization_id`. Timestamps. No `TenantScopedMixin` — a user belongs to orgs via membership.
- **`Role`** — `name` (enum: `individual_learner`, `instructor`, `content_editor`, `org_admin`, `system_admin`), `description`. Per FR-USER-04.
- **`Permission`** — `code` (e.g. `question:publish`), `description`.
- **`RolePermission`** — join table (role × permission).
- **`OrganizationMembership`** — user × organization × role (composite). A user can be an editor in Org A and a learner in Org B. Satisfies FR-USER-05 isolation: content queries scope by the user's active org membership.

#### `taxonomy/` — CISSP reference data. **Global, NOT tenant-scoped.**
`ExamBlueprint`, `ExamDomain`, `KnowledgePoint`, `Tag` are shared system-reference data, so they do **not** get `TenantScopedMixin`. (Books/chapters a user imports are tenant-scoped — see `question/`.)
- **`ExamBlueprint`** — `version_label` (e.g. "2024-04-15"), `effective_date`, `min_items` (100), `max_items` (150), `duration_minutes` (180), `passing_score` (700), `max_score` (1000), `is_current`. Per FR-TAX-02 and PRD §2.
- **`ExamDomain`** — `blueprint_id` FK, `number` (1–8), `name`, `weight_pct`. Composite unique (blueprint, number). Per FR-TAX-01.
- **`KnowledgePoint`** — self-referencing tree (`parent_id`), `name`, `description`. Binds to one or more domains via `KnowledgePointDomain` join (FR-TAX-04/05). Seed: empty tree.
- **`Tag`** — `name` (unique), `description`. Per FR-TAX-06.

#### `question/` — the bank. Tenant-scoped (an org owns its imported questions).
- **`Book`** / **`Chapter`** — tenant-scoped here (a user's "OSG 10th Edition" is their import, not global). `Book`: `title`, `edition`, `author`, `publisher`, `source_url`. `Chapter`: `book_id`, `order_index`, `title`.
- **`Question`** — `organization_id`, `question_type` (enum: `single_choice`, `multiple_choice`, `true_false`, `scenario` + reserved `ordering`/`drag_drop`/`hotspot` per FR-Q-05), `stem` (text), `stem_format` (`markdown`/`plain`), `difficulty` (1–5, nullable → default medium per §10.2), `language` (ISO code, default `en`), `status` (enum: `draft`/`pending_review`/`published`/`needs_revision`/`archived` per FR-Q-02), `source`, `license_status` (enum incl. `unconfirmed` per §10.2 — unconfirmed cannot enter the shared bank), `import_job_id` FK (nullable), `version` (int, increments on edit). Timestamps + AuditSubjectMixin. Soft-delete.
- **`QuestionOption`** — `question_id`, `order_index`, `content`, `content_format`, `is_correct` (bool), `explanation` (nullable, per-option — supports FR-ANS-04).
- **`Explanation`** — one per question: `correct_answer_rationale`, `key_point_summary`, `further_reading`. Per FR-ANS-03/04.
- **`QuestionMapping`** — join: `question_id`, `domain_id` (nullable), `chapter_id` (nullable), `knowledge_point_id` (nullable), `tag_id` (nullable). Multiple rows per question. Per FR-TAX-05.
- **`QuestionRevision`** — `question_id`, `revision_number`, `snapshot` (JSONB), `edited_by_id`, `edited_at`, `change_summary`. Per FR-Q-06.

#### `practice/` + `exam/` — sessions and the snapshot pattern. Tenant-scoped + user-owned.
- **`PracticeSession`**, **`PracticeAnswer`** — `PracticeAnswer` stores `question_snapshot` + `options_snapshot` (JSONB) so later edits to the question don't rewrite history (NFR-DATA-01). Also `user_answer` (JSONB), `is_correct`, `time_spent_ms`, `answered_at`.
- **`ExamSession`** — `session_kind` (`fixed`/`cat`), `status` (`in_progress`/`completed`/`aborted`/`auto_submitted`), plus blueprint/config refs.
- **`ExamAnswer`** — same snapshot discipline; additionally `ability_estimate_after` and `se_after` (nullable, for CAT in F).
- **`UserQuestionState`** — `user_id`, `question_id`, `is_bookmarked`, `is_flagged_review` (需复习), `is_mastered` (已掌握), `is_questioned` (有疑问), `note` (text), `mastery_level`. Unique per (user, question). Per FR-ANS-06/07.
- **`ImportJob`** — `organization_id`, `format` (csv/xlsx/json), `source`, `license_status`, `status` (enum: `pending`/`validating`/`previewing`/`importing`/`completed`/`failed`/`partial`), `total_rows`, `success_count`, `error_count`, `error_report` (JSONB), `initiated_by_id`, timestamps. Per FR-IMP-07/08. **Table exists in A; the import pipeline is sub-project C.**

#### `admin/`
- **`AuditLog`** — `actor_id` (nullable, for system actions), `organization_id` (nullable), `action` (enum: `login`/`import`/`edit`/`publish`/`delete`/`permission_change`/...), `entity_type`, `entity_id`, `details` (JSONB), `ip_address`, `occurred_at`. Per NFR-DATA-05/FR-ADMIN-06. **Table + a `log_audit()` helper exist in A; actual writes from real actions come with B/C.**
- **`SchemaMeta`** — `key`, `value`. Tracks `seed_version` for deterministic re-seed behavior.

### 3.3 Cross-cutting patterns, made concrete

**Snapshots (NFR-DATA-01):** `PracticeAnswer`/`ExamAnswer` carry `question_snapshot`/`options_snapshot` JSONB captured at answer time. A single producer `snapshot_question(question) -> dict` builds a frozen, minimal representation; the blob format can evolve inside JSONB without a migration. Snapshot columns exist in A so B/C/D can write to them.

**Soft-delete (NFR-DATA-02):** `SoftDeleteMixin.deleted_at`. Default query scope excludes soft-deleted rows; `with_deleted()` escape hatch for admin views. Soft-deleting a `Question` marks only the question row — `QuestionOption`/`PracticeAnswer`/`ExamAnswer` (and their snapshots) are untouched, preserving history.

### 3.4 Out of scope for A (explicitly deferred)
Auth endpoints, JWT logic, password-hashing logic (column only), import pipeline logic, practice/exam business logic, CAT engine, analytics, admin UI, Pydantic request/response schemas for business endpoints, background worker.

## 4. Migrations

Single Alembic env, `target_metadata = Base.metadata` over all model subpackages. One initial revision creates all ~22 tables, Postgres `ENUM` types, UUID PKs with `gen_random_uuid()` server defaults, FKs, and composite/unique indexes:

- `users.email` functional unique index on `lower(email)`
- `organizations.slug` unique
- `exam_domains (blueprint_id, number)` unique
- `organization_memberships (user_id, organization_id, role_id)` composite
- `questions (organization_id, status)` + `(organization_id, deleted_at)` (every list query filters by tenant + status + not-deleted)
- FK indexes on `question_mappings`, `question_revisions`, `user_question_states`

Down-migration drops in reverse dependency order. Autogenerate is the default; hand-edit only for ENUM creation order and the case-insensitive email index (which autogenerate mishandles).

## 5. Seeding (`backend/app/db/seed.py`)

Idempotent seed runnable via a `post_upgrade` Alembic hook **or** `python -m app.db.seed`. Two data classes:

1. **System reference (global):**
   - The `personal` organization.
   - The `2024-04-15` `ExamBlueprint` (100/150 items, 180 min, 700/1000).
   - All 8 `ExamDomain` rows with PRD §2 weights: 16/10/13/13/13/12/13/10.
   - The 5 `Role` rows.
   - Base `Permission` + `RolePermission` matrix (permission codes defined now; enforcing endpoints arrive in B–H).
   - Idempotent — re-running upserts, never duplicates. Guarded by `SchemaMeta.seed_version`.
2. **Not seeded:** questions, books, KPs, users (beyond what auth needs in B), tags. Runtime data.

## 6. Testing (`backend/tests/`)

Pytest + a Postgres-backed test DB (not SQLite — UUID/JSONB/ENUM need real Postgres), created/dropped per session via `conftest.py` fixtures, rolled back per test. Three tiers:

1. **Model tests** — mixin columns present on the right tables; defaults fire (`created_at` on insert); `deleted_at` excluded by default query; tenant FK enforced; `question_snapshot` round-trips through JSONB.
2. **Migration tests** — `alembic upgrade head` then `alembic downgrade base` succeeds on a clean DB; **autogenerate produces no diff** against current models (catches model/migration drift — the highest-value test for a foundations sub-project).
3. **Seed tests** — running `seed.py` produces exactly 1 `personal` org, 1 current blueprint, 8 domains summing weights to 100%, 5 roles; re-running is a no-op (idempotency).

Plus one **integration smoke test**: FastAPI app boots, `GET /health` returns `{status: ok, db: ok, redis: ok}`.

Frontend: no automated tests in A beyond `npm run build` passing. The placeholder page hitting `/health` is verified by the integration smoke test.

## 7. "Done" criteria (acceptance)

1. `git init` + initial commit of the scaffolding.
2. `docker compose up` brings Postgres, Redis, backend, frontend all healthy.
3. `alembic upgrade head` creates all ~22 tables cleanly; `alembic downgrade base` reverses them.
4. `python -m app.db.seed` populates system reference data idempotently.
5. `pytest` green (model + migration-no-drift + seed + `/health` smoke).
6. `npm run build` succeeds; placeholder page renders.
7. `CLAUDE.md` updated to reflect the now-real layout and commands (flip "planned" → actual).

## 8. Risks (from PRD §15, scoped to this sub-project)

- **Autogenerate vs. hand-written ENUM/UUID/index nuances** — mitigated by the no-drift migration test.
- **Snapshot column design locking in too early** — mitigated by keeping snapshots a minimal JSONB blob with a single `snapshot_question()` producer; format evolves inside the blob.
- **Over-modeling (~22 tables for "foundations")** — accepted trade-off: PRD §15 mandates snapshot/soft-delete/tenant/audit early, and retrofitting later is the expensive refactor it warns against. Tables with no logic yet (`ImportJob`, `ExamSession`) are empty shells their owning sub-projects will fill.
