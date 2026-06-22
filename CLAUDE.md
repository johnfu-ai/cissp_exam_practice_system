# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current State

**Sub-project A (Foundations & data model) is implemented and runnable.** The full stack starts with `docker compose up -d --build` and is verified healthy: backend `/health` returns `{"status":"ok","db":"ok","redis":"ok"}`, the frontend home page renders that status, the Alembic initial migration creates 26 tables, and the idempotent seed populates the personal org, the 2024-04-15 blueprint, 8 CISSP domains, 5 roles, and the permission matrix.

What exists now: backend (FastAPI + SQLAlchemy 2.x + Alembic), 27 ORM models across 6 bounded contexts, `/health` endpoint, **auth & RBAC** (`/api/auth/{register,login,refresh,logout,me,reset-password}`, JWT access + opaque refresh tokens in Redis, bcrypt passwords, login lockout, permission-based `require_permission` dependency), **ETL import pipeline** (`/api/etl/*` preview/commit/rollback/run two-phase lifecycle, seeded osg10 dataset + chapter→domain mappings), **question bank CRUD + lifecycle** (`/api/questions` create/read/update/delete, `/api/questions/{id}/review` state machine submit/approve/request_changes/archive/restore, `/api/questions/{id}/revisions` history with pre-edit snapshots, `/api/questions/{id}/feedback` correction feedback, plus read-only `/api/{domains,books,knowledge-points}` taxonomy API), idempotent seed (bootstraps a `system_admin` user), migration + model + auth + etl + question tests (122 passing); frontend (Next.js 14 with login/register/logout pages, Zustand auth store, typed API client with silent refresh). What does NOT exist yet: practice/exam APIs, CAT engine, analytics & admin UI, interactive import, taxonomy write/admin — these are later sub-projects (D–H).

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
- **CAT is a study tool, not an official prediction** (PRD §11): the MVP CAT must be rule-driven with simplified ability estimation. Do not make 3PL IRT a P0 dependency — full IRT is a Phase 5 enhancement. `backend/app/services/cat_engine.py` does not exist yet.
- **CAT exam rules** (when implemented): once submitted, an answer cannot be revised; no skipping; forward-only; medium-difficulty start item.

### Tests

- Tests use a real PostgreSQL DB, not SQLite. `tests/conftest.py` creates/drops a dedicated `cissp_test` database each session (isolated from the dev `cissp` DB) and uses per-test transaction rollback via nested SAVEPOINT.
- `tests/test_migrations.py` runs against a separate `cissp_migtest` DB (drop/create/upgrade per fixture) and includes a no-autogenerate-drift test — the highest-value guard. When you change models, run `alembic revision --autogenerate` and keep drift at zero (the test filters out the hand-written `uq_users_email_lower` index and throwaway `_test_*` tables).

## Reference

- PRD: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` (in Chinese) — product overview, roles, functional requirements (FR-*), non-functional requirements (NFR-*), data models (§9.4), core API surface (§9.5), import template & validation rules (§10), CAT strategy (§11), MVP scope (§12), and acceptance criteria (§14).
- Design spec (sub-project A): `docs/superpowers/specs/2026-06-21-foundations-and-data-model-design.md`.
- Implementation plan: `docs/superpowers/plans/2026-06-21-foundations-and-data-model.md`.
- Official CISSP exam baseline as of 2026-06-21: 3-hour CAT, 100–150 items, pass 700/1000, exam outline effective 2024-04-15. See PRD §2 for the 8-domain weight table.
