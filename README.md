# CISSP Exam Practice System

A CISSP exam preparation platform with a **WeChat mini-program learner client** and a web app,
a **Next.js admin portal**, and a **FastAPI** backend. Exam rules (domain weights, item counts,
duration, passing line) live in data via `ExamBlueprint`, not hard-coded constants.

> **Status (PRD v1.3 + P1 completeness).** Backend feature-complete (104+ endpoints, 8 routers).
> Learner clients cover paper-based practice/exam (paper imports), the wrong-question book,
> answer metadata (mapping/history/related/`is_questioned`), review, fixed/CAT exams, analytics,
> and settings. Next.js is **admin-only** (import with template/mapping, questions, taxonomy
> including chapter→domain mappings + KP↔domain bindings, admin, settings). Shared OpenAPI
> contract: [`openapi/openapi.json`](openapi/openapi.json).

## Features

- **WeChat mini program (CISSP Papers)** — native mini program: papers, practice/exam, wrong book, settings,
  wrong/bookmark review, fixed + CAT mock exams, dashboard analytics, bilingual question
  rendering, interface language en/zh, desktop keyboard shortcuts.
- **Next.js admin portal** — question bank editorial workflow, ETL import (template + field map),
  taxonomy (incl. chapter→domain ETL mappings and KP↔domain bindings), users/classes, CAT params,
  quality queue, audit, reports, language coverage.
- **Auth & RBAC** — JWT access + opaque Redis refresh (httpOnly cookie + body fallback for
  native clients), bcrypt, lockout, permission gates.
- **Practice / fixed exam / CAT** — snapshot-judged answers; CAT is a study tool with
  simplified ability estimation (≠ ISC2 official scoring).
- **Bilingual content** — en / zh / bilingual modes; in-runner toggle never advances CAT.

## Tech Stack

| Layer | Technology |
| ----- | ---------- |
| Learner (mobile) | Native WeChat mini program (`miniprogram/`) |
| Admin | Next.js 16, React 19, TypeScript, Tailwind v3, shadcn/ui |
| Backend | FastAPI 0.138, SQLAlchemy 2.x, Alembic, Pydantic Settings |
| Data | PostgreSQL 16, Redis 7 |
| Contract | OpenAPI 3.1 → `openapi/openapi.json` |

## Quick Start (Docker)

```bash
docker compose up -d --build
curl http://localhost:8000/health
curl http://localhost:3000/          # admin portal

cd mobile
flutter pub get && flutter gen-l10n
# Android emulator:
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
# Desktop / iOS sim:
flutter run --dart-define=API_BASE_URL=http://localhost:8000
```

Seed creates a `system_admin` user (dev password `admin` when `APP_ENV` is development).

## Local Development

### Backend (`backend/`)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload --port 8000
pytest
```

### Admin frontend (`frontend/`)

```bash
npm install
npm run dev            # http://localhost:3000
npm run test
npm run gen:api        # from ../openapi/openapi.json
```

### WeChat mini program (`miniprogram/`)

See [`miniprogram/README.md`](miniprogram/README.md).

```bash
cd miniprogram && npm test
dart test -p vm test/
```

### OpenAPI

```bash
cd backend && python -m app.scripts.export_openapi ../openapi/openapi.json
```

CI fails if `openapi/openapi.json` drifts from the live FastAPI schema.

## Architecture

```
WeChat mini program (learner)             Web app (learner + admin, browser)
              \                             /
               +-------- HTTPS / REST ------+
                            |
                         FastAPI
                   PostgreSQL + Redis
```

- **Learner UX** lives in the mini program AND the web app (FR-CLIENT-02/03).
- **Admin UX** lives only in Next.js (FR-CLIENT-03/06). Users without manage permissions see
  `/access-required` on the web portal.
- Access token: memory. Refresh: local storage (mini program) / httpOnly cookie (web), with body
  fallback on `/api/auth/refresh`.

### Repository layout

```
backend/           # FastAPI app + tests
frontend/          # Next.js admin portal
miniprogram/       # WeChat mini program learner client
openapi/           # Shared OpenAPI artifact
assets/ui_images/  # design mockups
docs/              # PRD + superpowers specs/plans
```

## Testing

```bash
cd backend && pytest
cd backend && pytest tests/test_e2e_acceptance.py   # §14 API acceptance paths
cd frontend && npm run test
cd mobile && dart test -p vm test/
./scripts/check_dart_api_drift.sh                   # OpenAPI ↔ Dart client drift
# With docker compose up:
./scripts/e2e_smoke.sh                              # health + login + practice smoke
```

### Production compose & backups

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
./scripts/backup.sh
./scripts/restore.sh <dump.sql.gz>
```

Ops runbook (TLS, SMTP, Sentry, incidents): [`docs/ops/production-runbook.md`](docs/ops/production-runbook.md)

## Documentation

- PRD: [`docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md`](docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md)
- Mock papers / mini program wave: [`docs/superpowers/specs/2026-09-25-mock-papers-wechat-design.md`](docs/superpowers/specs/2026-09-25-mock-papers-wechat-design.md)
- Dual-client gap closure: [`docs/superpowers/specs/2026-08-10-prd-apps-gap-closure-design.md`](docs/superpowers/specs/2026-08-10-prd-apps-gap-closure-design.md)
- P1 completeness: [`docs/superpowers/specs/2026-08-10-prd-p1-completeness-design.md`](docs/superpowers/specs/2026-08-10-prd-p1-completeness-design.md)
- Agent guidance: [`CLAUDE.md`](CLAUDE.md)

## Disclaimer

This is an independent study aid. It is **not affiliated with, endorsed by, or a substitute
for** ISC2 or the official CISSP examination. CAT scoring is a simplified study estimate and
does not reflect official ISC2 scoring. CISSP® and ISC2® are registered trademarks of ISC2, Inc.
