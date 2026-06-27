# CISSP Exam Practice System

A full-stack web application for CISSP exam preparation: a question bank with editorial
workflow, practice sessions, fixed-form and computer-adaptive (CAT) mock exams, personal
learning analytics, and an admin backoffice — built on a data-driven exam blueprint so the
official CISSP rules (domain weights, item counts, duration, passing line) live in data, not code.

> **Status.** Feature-complete and runnable. The full PRD backend scope is implemented and
> tested — **104 endpoints across 8 routers, 427 passing backend tests, zero migration drift**.
> The interactive frontend is fully built: all 13 routes (dashboard, analytics, practice,
> review, fixed + CAT exam, import, questions, taxonomy, admin) with an Apple-inspired design
> system and bilingual (English / 中文) question content throughout — **75 frontend tests**.

## Features

- **Auth & RBAC** — JWT access + opaque Redis refresh tokens, bcrypt passwords, login
  lockout, permission-based authorization (`require_permission`).
- **Question bank** — CRUD plus an editorial lifecycle state machine (submit / approve /
  request-changes / archive / restore), revision history with pre-edit snapshots, and
  correction feedback.
- **Taxonomy** — exam blueprints & domains, books & chapters, a knowledge-point tree with
  cycle prevention, KP↔domain bindings, and tags. Read-only taxonomy API for clients.
- **ETL import** — two-phase preview → commit → rollback import pipeline for question datasets.
- **Practice** — scoped session creation, answer judging from a question snapshot,
  pause/resume, bookmarks/flags/notes, and a finish summary with per-domain breakdown.
- **Fixed exam** — domain-weighted auto-assembly from the current blueprint, timed
  feedback-free delivery with lazy auto-submit, scaled score / pass report, and history trend.
- **CAT exam** — a rule-driven adaptive engine with simplified ability estimation
  (forward-only, non-revisable items, ability-matched selection, convergence/time/count
  termination). **It is a study tool, not an official ISC2 score prediction.**
- **Learning analytics** — personal dashboard, per-domain mastery, 30/90-day trends, weak-area
  detection, error-type breakdown, and a weekly review recommendation.
- **Admin backoffice** — user & class management, CAT-parameter versioning, a content-quality
  queue, an audit-log viewer, and operational reports.
- **Bilingual content** — questions carry English + 中文 translations; users pick a default
  language mode (en / zh / bilingual) and toggle it live in practice/exam runners without
  refetching or advancing the item (FR-LANG-01..10).

## Tech Stack

| Layer        | Technology                                                              |
| ------------ | ----------------------------------------------------------------------- |
| Frontend     | Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, DM Sans, Zustand, Vitest |
| Backend      | FastAPI, SQLAlchemy 2.x, Alembic, Pydantic Settings                     |
| Data / Cache | PostgreSQL 16, Redis 7                                                   |
| Tooling      | Docker Compose, pytest, ESLint                                          |

## Quick Start (Docker)

```bash
docker compose up -d --build      # build + start postgres, redis, backend, frontend
docker compose ps                 # check health

curl http://localhost:8000/health # -> {"status":"ok","db":"ok","redis":"ok"}
curl http://localhost:3000/       # frontend
```

The seed bootstraps a personal organization, the 2024-04-15 exam blueprint, the 8 CISSP
domains, roles, the permission matrix, and a `system_admin` user.

## Local Development

### Backend (`backend/`)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head                          # apply migrations
python -m app.db.seed                         # idempotent seed (safe to re-run)
uvicorn app.main:app --reload --port 8000     # dev server
pytest                                        # run tests
```

### Frontend (`frontend/`)

```bash
npm install
npm run dev            # http://localhost:3000
npm run build          # production build
npm run lint
npm run test           # Vitest
```

### Configuration

Backend settings are read from environment (see `backend/.env` or `docker-compose.yml`):
`DATABASE_URL`, `REDIS_URL`, `jwt_secret` (change from default), `access_token_expire_minutes`,
`refresh_token_expire_days`, `bcrypt_rounds`, `login_lockout_threshold`,
`login_lockout_window_minutes`, `cors_origins`, `seed_admin_email`, `seed_admin_password`.

## Architecture

- **Service-layer backend** — API routes are thin and delegate to service modules
  (`app/services/*`) that own business logic and DB access.
- **Tenant scoping** — content tables (questions, books, sessions, import jobs, …) are
  `organization_id`-scoped; taxonomy (blueprints, domains, knowledge points, tags) is global.
- **Exam config is data, not code** — domain weights, item-count ranges, duration, passing
  line, and effective dates live in `ExamBlueprint` / `ExamDomain`.
- **Historical integrity via snapshots** — completed practice/exam answers store a snapshot of
  the question and options at answer time, so later edits never alter past records.
- **Soft delete only** — deleting a question never breaks historical answer records.
- **Audit logging** — logins, imports, edits, publishes, deletes, and permission changes are
  recorded to `AuditLog`.

### Repository layout

```
backend/
  app/
    api/           # 8 routers: auth, etl, questions, taxonomy, practice, exam, analytics, admin
    services/      # business logic + DB access
    models/        # ORM models across 6 bounded contexts
    db/            # base mixins, session, seed
    alembic/       # migrations
  tests/           # pytest suite (real PostgreSQL, per-test SAVEPOINT rollback)
frontend/
  src/
    app/           # Next.js App Router routes
    features/      # feature modules (e.g. practice)
    components/ui/ # UI primitives
    lib/           # API client, query keys, types
docs/              # PRD + design specs + implementation plans
```

## Testing

Backend tests run against a real PostgreSQL database (a dedicated `cissp_test` DB, isolated
from dev, with per-test transaction rollback via nested SAVEPOINT). A migration test guards
against autogenerate drift — the highest-value check when models change.

```bash
cd backend && pytest
cd frontend && npm run test
```

## Documentation

- Product requirements: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` (source of truth for scope).
- Design specs & implementation plans: `docs/superpowers/specs/` and `docs/superpowers/plans/`.
- Contributor / agent guidance: `CLAUDE.md`.

## Disclaimer

This is an independent study aid. It is **not affiliated with, endorsed by, or a substitute
for** ISC2 or the official CISSP examination. CAT scoring is a simplified study estimate and
does not reflect official ISC2 scoring.
