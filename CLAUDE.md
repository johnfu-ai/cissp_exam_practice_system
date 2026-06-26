# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current State

**Sub-project A (Foundations & data model) is implemented and runnable.** The full stack starts with `docker compose up -d --build` and is verified healthy: backend `/health` returns `{"status":"ok","db":"ok","redis":"ok"}`, the frontend home page renders that status, the Alembic initial migration creates 26 tables, and the idempotent seed populates the personal org, the 2024-04-15 blueprint, 8 CISSP domains, 5 roles, and the permission matrix.

What exists now: backend (FastAPI + SQLAlchemy 2.x + Alembic), 27 ORM models across 6 bounded contexts, `/health` endpoint, **auth & RBAC** (`/api/auth/{register,login,refresh,logout,me,reset-password}`, JWT access + opaque refresh tokens in Redis, bcrypt passwords, login lockout, permission-based `require_permission` dependency), **ETL import pipeline** (`/api/etl/*` preview/commit/rollback/run two-phase lifecycle, seeded osg10 dataset + chapter→domain mappings), **question bank CRUD + lifecycle** (`/api/questions` create/read/update/delete, `/api/questions/{id}/review` state machine submit/approve/request_changes/archive/restore, `/api/questions/{id}/revisions` history with pre-edit snapshots, `/api/questions/{id}/feedback` correction feedback, plus read-only `/api/{domains,books,knowledge-points}` taxonomy API), **taxonomy admin** (`/api/admin/blueprints` + `/domains` CRUD with set-current and refuse-delete-on-reference guards; `/api/books` + `/chapters` tenant-scoped CRUD; `/api/knowledge-points` tree CRUD with cycle prevention; `/api/admin/knowledge-points/{id}/domains` KP↔domain bindings; `/api/tags` CRUD — all write routes gated by `admin:manage_taxonomy`, read routes by `question:read`, service layer in `app/services/taxonomy_admin.py` with `ValidationError`/`NotFound`/`ConflictError` mapped to 422/404/409), **practice API** (`/api/practice/sessions` create + scoped delivery + answer judging from snapshot + pause/resume + finish summary with per-domain breakdown + wrong-question list; `/api/practice/questions/{id}/state` bookmarks/flags/notes; service layer `app/services/practice.py` with ValidationError/NotFound/ConflictError → 422/404/409; all gated by `practice:read`), **fixed exam API** (`/api/exam/sessions` create with domain-weighted auto-assembly from the current ExamBlueprint, timed feedback-free delivery with lazy auto-submit, revisable answers judged from snapshot, `/api/exam/sessions/{id}/finish` + `/report` (scaled score/pass/accuracy/per-domain/time/wrong-question list), `/api/exam/sessions/{id}/review` unified post-exam review, `/api/exam/history` trend; service layer `app/services/exam.py` with ValidationError/NotFound/ConflictError → 422/404/409; all gated by `exam:read`), **CAT exam API** (`/api/exam/sessions` with `{"kind":"cat"}` creates a rule-driven adaptive exam reusing ExamSession (`session_kind=cat`) + the `config` JSONB column; pure engine `app/services/cat_engine.py` (simplified ability estimation — NOT full 3PL IRT, which is Phase 5: `update_ability`/`sem`/`decide_termination`/`select_first_item`/`select_next_item`/`scaled_score`/`readiness_level`/`DISCLAIMER`); CAT answers are non-revisable/non-skippable/forward-only via position check with NO upsert (differs from fixed exam); medium-difficulty start, ability-matched next item with domain-weight coverage + knowledge-point/source anti-cluster; termination at min/max items, time-up (lazy auto-submit), or ability-estimate convergence (early-stop ≥100); `/api/exam/sessions/{id}/next` CAT-only delivery (409 for fixed); report carries ability estimate/CI/SEM/readiness_level/disclaimer (study tool, ≠ ISC2 official scoring — FR-CAT-10); `finish`/`report`/`review`/`history` branched on session kind, ability-based scoring for CAT; `_INTERNAL_CONFIG_KEYS` stripped from session serialization), **personal learning analytics** (`/api/analytics/*` dashboard/domains/trend/weak-areas/error-types/recommendation/report — personal-scoped aggregations over practice+exam answers merged in Python, mastery derived from accuracy, weak-area threshold accuracy<0.6 & answered≥3, 30/90-day trend (422 otherwise), weekly review recommendation with mastered-exclusion, single-call `/report` composition; new `ErrorType` enum (5 types) + nullable `UserQuestionState.error_type` column exposed via the existing `PUT /api/practice/questions/{id}/state`; graceful degradation for empty users / missing blueprint (200, not 422); service layer `app/services/analytics.py`; all gated by `practice:read`), **admin backoffice** (`/api/admin/*` user + class management FR-ADMIN-03, CAT-param versioning FR-ADMIN-04, content-quality queue FR-ADMIN-05, audit-log viewer FR-ADMIN-06, operational reports FR-ADMIN-07; thin router `app/api/admin.py` delegating to `app/services/admin.py` with `AdminError`/`ValidationError`/`NotFound`/`ConflictError` → 422/404/409; org-scoped for org_admin / global for system_admin via `_admin_org_scope`; audit-on-every-mutation; three new tables `CatParamsVersion`/`Class`/`ClassMembership`; new `admin:view_reports` permission; `exam.py` snapshots the current `CatParamsVersion` into CAT session `config["cat_params"]` at creation with `cat_engine.DEFAULT_PARAMS` fallback — NFR-DATA-01; permission codes: users/classes=`admin:manage_users`, cat-params=`admin:manage_taxonomy`, quality=`question:publish`, audit=`admin:view_audit`, reports=`admin:view_reports`; cross-org target lookup → 404, cross-org `org_id` param → 422; `window_days` ∈ {30,90} else 422), idempotent seed (bootstraps a `system_admin` user), migration + model + auth + etl + question + taxonomy-admin + practice + exam + cat + analytics + admin tests (366 passing); frontend (Next.js 14 with login/register/logout pages, Zustand auth store, typed API client with silent refresh). **The full PRD functional backend scope (FR-* through FR-ADMIN-07) is implemented and merged to `master` — 104 endpoints across 8 routers, 366 backend tests, zero migration drift.**

**The interactive frontend (sub-project I) is now implemented** over the existing APIs — every PRD page in §8.1 exists and the full stack is e2e-verified runnable (`docker compose up -d`, then import → publish → practice → fixed exam → CAT all succeed against the running backend). Frontend surface: `/dashboard` + `/analytics` (personal learning analytics over `/api/analytics/*`, dependency-light inline SVG/CSS charts), `/practice` (create/runner/summary) + `/review` (wrong/bookmarked/flagged re-practice launchers over subset-scoped sessions; runner now sets mastered/error-type/notes), `/exam` (fixed runner with countdown + lazy auto-submit + revisable positional answers + question palette; forward-only CAT runner over `/next` with a persistent study-tool disclaimer; shared report surfacing CAT ability/CI/SEM/readiness + `DISCLAIMER`; review + history with localStorage resume), `/import` (dataset preview → commit/rollback wizard, `question:import`), `/questions` (filterable list + create/edit editor + review state machine + revisions + correction feedback), `/taxonomy` (blueprints+domains / books+chapters / knowledge-points tree / tags, `admin:manage_taxonomy`), `/admin` (users / classes / CAT-param versions / quality queue / audit-log viewer / operational reports — tabs gated per-permission). Sidebar has a permission-gated "Manage" section. 49 frontend Vitest tests (pure helpers + state machines + components). Decisions made along the way: charts are hand-rolled (no Recharts dep); the import UI is dataset-driven (matches the actual ETL pipeline — there is no file-upload endpoint); `docker-compose.yml` bind-mounts `./docs/questions` into the backend so the seeded osg10 dataset resolves in-container. No new backend sub-projects are required by the PRD.

Working-tree dev conveniences (uncommitted, intentionally kept): `seed.py` resets the admin password to the configured `seed_admin_password` on every restart (so `admin/admin` stays usable in dev), and the login page has a one-click "Dev login (admin/admin)" button.

**Bilingual question content & language-mode selection (FR-LANG-01..10, PRD v1.1)** is implemented on branch `feat/language-selection`. Data model: one `Question` row holds structural fields + `available_languages` (ARRAY(String(5)), GIN-indexed); a `question_translations` table holds per-language stem/option-content/explanation (`(question_id, language)` unique); `QuestionOption` is canonical (order_index + is_correct only — the language-independent answer key); the `Explanation` table is dropped; `User.language_mode` (en|zh|bilingual) is the default preference; `QuestionExternalKey` is unique on `(dataset_slug, external_id)`. Sessions store `language_mode` in their existing `config` JSONB. Delivery (`/api/practice/.../questions/{pos}`, `/api/exam/.../questions/{pos}`, `/api/exam/.../next`) returns BOTH languages (`Localized {en,zh}`) so the client toggles mode instantly without refetching — including CAT (the toggle is pure client state; it never calls `/next`, so it never advances the item). Candidate filters (`app/services/i18n.py::language_filter`) exclude questions missing the requested language (FR-LANG-04). Snapshots (`snapshot_question(question, translations, options, *, language_mode)`) freeze all translations + the mode (FR-LANG-07); judging still reads `is_correct` from the snapshot. New: `GET/PUT /api/users/me/preferences`; `language_mode` in `UserOut`/`/me`/`/login`/`/register`; `GET /api/questions/language-coverage` + `/api/admin/questions/language-coverage` (admin:view_reports); `missing_language` list filter (FR-LANG-10). ETL writes one Question + en/zh translations per external_id (the migration MERGES old en/zh row pairs into single bilingual questions, repointing child FKs and deduping `user_question_states` by `updated_at`). Frontend: `<BilingualText>` + sidebar default-mode control; practice/exam runners have an in-runner mode toggle (selections/timer/progress preserved); question editor has English/中文 tabs with publish-completeness validation (FR-LANG-09). 427 backend tests + 67 frontend tests, zero migration drift; full stack e2e-verified (import → publish → practice/fixed/CAT in all three modes). Known follow-ups (not blocking): PRD §10.2 partial-zh completeness validation; `EtlDataset.languages` no longer gates zh writing; `BilingualText` duplicate-render edge case when one language is null in bilingual mode.

**Auth env vars** (in `backend/.env` or compose): `jwt_secret` (change from default), `access_token_expire_minutes`, `refresh_token_expire_days`, `bcrypt_rounds`, `login_lockout_threshold`, `login_lockout_window_minutes`, `cors_origins` (comma-separated), `seed_admin_email`, `seed_admin_password` (if unset, the seed prints a randomly generated admin password once).

The PRD remains the source of truth for scope. Read it before designing later sub-projects.

## Tech Stack (actual)

- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS. Server components by default; only add `'use client'` where interactivity is needed.
- **Backend**: FastAPI, SQLAlchemy 2.x (`DeclarativeBase` + mixins), Alembic migrations, Pydantic Settings.
- **Database / Cache**: PostgreSQL 16, Redis 7 (sessions, rate limiting, CAT transient state).
- Versions are pinned: see `backend/requirements.txt` and `frontend/package.json`. Docker images use Python 3.11-slim and Node 20-slim (local dev may use newer runtimes).

## Commands

Frontend (`frontend/`):
```bash
npm install
npm run dev            # port 3000
npm run build          # production build
npm run lint           # ESLint
npm run test           # Vitest
npm run test:watch
```

Backend (`backend/`):
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000   # dev server
pytest                                       # all tests
pytest tests/ -k "test_name"                 # single test
alembic upgrade head                         # apply migrations
alembic revision --autogenerate -m "desc"    # create migration
python -m app.db.seed                        # idempotent seed (safe to re-run)
```

Docker (full stack):
```bash
docker compose up -d --build      # build + start postgres, redis, backend, frontend
docker compose ps                 # check health
docker compose logs -f backend    # follow backend logs
curl http://localhost:8000/health # backend smoke
curl http://localhost:3000/       # frontend smoke
```

## Architecture (implemented)

### Backend layout

- `app/main.py` — `create_app()` factory; `GET /health` checks DB + Redis connectivity.
- `app/core/config.py` — `Settings(BaseSettings)`; reads `DATABASE_URL`, `REDIS_URL`, JWT settings from env.
- `app/db/base.py` — `Base(DeclarativeBase)` plus reusable mixins: `UUIDPrimaryKey` (`gen_random_uuid()` server default), `TimestampMixin`, `SoftDeleteMixin` (`deleted_at`), `TenantScopedMixin` (`organization_id` FK, NOT NULL on content tables), `AuditSubjectMixin` (`created_by_id`/`updated_by_id`/`reviewed_by_id`).
- `app/db/queries.py` — `not_deleted(model)` helper (filters `deleted_at IS NULL`). Use this for soft-delete queries.
- `app/db/seed.py` — idempotent seed guarded by `SchemaMeta.seed_version`. `run_seed(session)` + `main()` CLI.
- `app/db/session.py` — engine/sessionmaker/session factory.
- `app/models/` — one module per bounded context: `auth`, `taxonomy`, `question`, `practice`, `exam`, `admin`, plus `enums.py`. All registered via `app/models/__init__.py`.
- `app/services/snapshot.py` — `snapshot_question(question, options) -> dict` for historical-integrity snapshots.
- `app/services/audit.py` — `log_audit(session, *, action, ...)` helper.
- `app/alembic/` — `env.py` respects an explicitly-set `sqlalchemy.url` (so tests can target a different DB); `versions/66bec070d8fc_initial_schema.py` is the initial migration.

### Cross-cutting rules (carry into later sub-projects)

- **Service-layer backend**: API routes delegate to service modules that own business logic and DB access. Never put business logic directly in route handlers.
- **Tenant scoping**: content tables (questions, books, chapters, practice/exam sessions, import jobs, etc.) are `organization_id`-scoped and NOT NULL. Taxonomy (`ExamBlueprint`, `ExamDomain`, `KnowledgePoint`, `KnowledgePointDomain`, `Tag`) is GLOBAL (shared across orgs).
- **Native PostgreSQL ENUMs**: defined in `app/models/enums.py` and created as real `CREATE TYPE` in the migration. The initial migration's `downgrade()` explicitly drops these types (autogen `drop_table` does not).
- **UUID PKs**: all PKs are UUID with `gen_random_uuid()` server default. Email uniqueness is case-insensitive via a hand-written functional index `uq_users_email_lower` (not expressible in column metadata).
- **Historical integrity via snapshots**: completed practice/exam answers store a snapshot of the question and options at answer time (`PracticeAnswer`, `ExamAnswer` JSONB columns), so later edits to a question never change past records. Use `snapshot_question()`.
- **Soft delete only**: deleting a question must not break historical answer records. Filter live rows with `not_deleted(model)`.
- **Exam config is data, not code**: domain weights, question-count ranges, exam duration, passing line, and effective dates live in `ExamBlueprint`/`ExamDomain`. Do not hardcode CISSP domain weights or the 100–150 / 3-hour / 700-pass rules.
- **Audit logging**: logins, imports, edits, publishes, deletes, and permission changes go to `AuditLog` via `log_audit()`.
- **CAT is a study tool, not an official prediction** (PRD §11): the MVP CAT must be rule-driven with simplified ability estimation. Do not make 3PL IRT a P0 dependency — full IRT is a Phase 5 enhancement. `backend/app/services/cat_engine.py` implements the rule-driven MVP engine (pure module, no SQLAlchemy); CAT reports MUST surface `cat_engine.DISCLAIMER` (≠ ISC2 official scoring — FR-CAT-10).
- **CAT exam rules** (when implemented): once submitted, an answer cannot be revised; no skipping; forward-only; medium-difficulty start item.

### Tests

- Tests use a real PostgreSQL DB, not SQLite. `tests/conftest.py` creates/drops a dedicated `cissp_test` database each session (isolated from the dev `cissp` DB) and uses per-test transaction rollback via nested SAVEPOINT.
- `tests/test_migrations.py` runs against a separate `cissp_migtest` DB (drop/create/upgrade per fixture) and includes a no-autogenerate-drift test — the highest-value guard. When you change models, run `alembic revision --autogenerate` and keep drift at zero (the test filters out the hand-written `uq_users_email_lower` index and throwaway `_test_*` tables).

## Reference

- PRD: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` (in Chinese) — product overview, roles, functional requirements (FR-*), non-functional requirements (NFR-*), data models (§9.4), core API surface (§9.5), import template & validation rules (§10), CAT strategy (§11), MVP scope (§12), and acceptance criteria (§14).
- Design spec (sub-project A): `docs/superpowers/specs/2026-06-21-foundations-and-data-model-design.md`.
- Implementation plan: `docs/superpowers/plans/2026-06-21-foundations-and-data-model.md`.
- Official CISSP exam baseline as of 2026-06-21: 3-hour CAT, 100–150 items, pass 700/1000, exam outline effective 2024-04-15. See PRD §2 for the 8-domain weight table.
