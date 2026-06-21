# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current State

**This repository is pre-code.** It currently contains only this file and the product spec at `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md`. There is no `frontend/`, `backend/`, `package.json`, `requirements.txt`, or any build/test setup yet. Do not assume the commands or file paths below exist — they are the *planned* layout. Verify against the actual tree before running anything, and update this file as real code lands.

The PRD is the source of truth for scope, priorities, and constraints. Read it before designing data models, APIs, or the CAT algorithm. The rest of this file summarizes the parts most likely to cause rework if ignored.

## Planned Tech Stack

- **Frontend**: Next.js (App Router), TypeScript, Tailwind CSS. Server components by default; only add `'use client'` where interactivity is needed.
- **Backend**: FastAPI (Python 3.11+), SQLAlchemy ORM, Alembic migrations.
- **Database / Cache**: PostgreSQL, Redis (sessions, rate limiting, CAT transient state).
- Planned supporting libs: TanStack Query, Zustand or React Context, React Hook Form + Zod, shadcn/ui, Celery/RQ/Arq for background import/dedup/report jobs.

## Architecture Constraints (from the PRD)

These are design rules the PRD mandates. They cut across multiple files and are easy to get wrong if discovered late:

- **Service-layer backend**: API routes delegate to service modules that own business logic and DB access. Never put business logic directly in route handlers.
- **Exam config is data, not code**: domain weights, question-count ranges, exam duration, passing line, question types, language, and effective dates must be maintable by admins (the `ExamBlueprint` / `ExamDomain` models). Do not hardcode CISSP domain weights or the 100–150 / 3-hour / 700-pass rules.
- **Historical integrity via snapshots**: completed practice/exam answers must store a snapshot of the question and options at answer time (`PracticeAnswer`, `ExamAnswer`), so later edits to a question never change past records.
- **Soft delete only**: deleting a question must not break historical answer records.
- **Provenance & licensing**: every question records source, authorization status, and import batch. Questions without confirmed authorization must not enter the shared bank. Pages must display CISSP/ISC2 trademark notices and state the product is not the official ISC2 exam platform.
- **Audit logging**: logins, imports, edits, publishes, deletes, and permission changes are written to `AuditLog`.
- **CAT is a study tool, not an official prediction**: per PRD §11, the MVP CAT must be **rule-driven with simplified ability estimation** (1–5 difficulty, ability rises/falls with correctness, next-item picked by difficulty + domain-weight coverage, anti-repeat heuristics, early-stop after 100 items if ability is clearly above/below threshold, hard stop at 150 or 3h). Do **not** make 3PL IRT a P0 dependency — the PRD explicitly warns that IRT without calibration data produces untrustworthy results. Full IRT (a/b/c/theta/SE, exposure control, calibration) is a Phase 5 enhancement. The existing claim that the CAT engine "implements IRT" is aspirational, not current.
- **CAT exam rules**: once submitted, an answer cannot be revised; no skipping; forward-only; medium-difficulty start item.

## Commands (planned, not yet present)

These will apply once scaffolding is created. Do not run them blindly today.

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
```

Docker (once a `docker-compose.yml` exists):
```bash
docker compose up -d
docker compose logs -f backend
```

## Reference

- Spec: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` (in Chinese) — product overview, roles, functional requirements (FR-*), non-functional requirements (NFR-*), data models (§9.4), core API surface (§9.5), import template & validation rules (§10), CAT strategy (§11), MVP scope (§12), and acceptance criteria (§14).
- Official CISSP exam baseline as of 2026-06-21: 3-hour CAT, 100–150 items, pass 700/1000, exam outline effective 2024-04-15. See PRD §2 for the 8-domain weight table and source links.
