# CISSP Exam Practice System

A CISSP exam preparation platform with a **Flutter learner client** (Android, iOS, Windows),
a **Next.js admin portal**, and a **FastAPI** backend. Exam rules (domain weights, item counts,
duration, passing line) live in data via `ExamBlueprint`, not hard-coded constants.

> **Status (PRD v1.3).** Backend feature-complete (104 endpoints, 8 routers). Flutter learner
> MVP covers auth, practice, review, fixed/CAT exams, analytics, and settings against the same
> APIs. Next.js is **admin-only** (import, questions, taxonomy, admin, settings). Shared OpenAPI
> contract: [`openapi/openapi.json`](openapi/openapi.json).

## Features

- **Flutter learner (CISSP Compass)** — one codebase for Android / iOS / Windows: practice,
  wrong/bookmark review, fixed + CAT mock exams, dashboard analytics, bilingual question
  rendering, interface language en/zh.
- **Next.js admin portal** — question bank editorial workflow, ETL import, taxonomy, users,
  CAT params, quality queue, audit, reports.
- **Auth & RBAC** — JWT access + opaque Redis refresh (httpOnly cookie + body fallback for
  native clients), bcrypt, lockout, permission gates.
- **Practice / fixed exam / CAT** — snapshot-judged answers; CAT is a study tool with
  simplified ability estimation (≠ ISC2 official scoring).
- **Bilingual content** — en / zh / bilingual modes; in-runner toggle never advances CAT.

## Tech Stack

| Layer | Technology |
| ----- | ---------- |
| Learner | Flutter 3.32 (Riverpod, GoRouter, Dio) — Android, iOS, Windows |
| Admin | Next.js 16, React 19, TypeScript, Tailwind v3, shadcn/ui |
| Backend | FastAPI 0.138, SQLAlchemy 2.x, Alembic, Pydantic Settings |
| Data | PostgreSQL 16, Redis 7 |
| Contract | OpenAPI 3.1 → `openapi/openapi.json` |

## Quick Start (Docker + Flutter)

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

### Flutter learner (`mobile/`)

See [`mobile/README.md`](mobile/README.md).

```bash
cd mobile && flutter analyze
dart test -p vm test/
```

### OpenAPI

```bash
cd backend && python -m app.scripts.export_openapi ../openapi/openapi.json
```

CI fails if `openapi/openapi.json` drifts from the live FastAPI schema.

## Architecture

```
Flutter learner (Android/iOS/Windows)     Next.js admin (browser)
              \                             /
               +-------- HTTPS / REST ------+
                            |
                         FastAPI
                   PostgreSQL + Redis
```

- **Learner UX** lives only in Flutter (FR-CLIENT-02).
- **Admin UX** lives only in Next.js (FR-CLIENT-03/06). Users without manage permissions see
  `/access-required` on the web portal.
- Access token: memory. Refresh: secure storage (Flutter) / httpOnly cookie (web), with body
  fallback on `/api/auth/refresh`.

### Repository layout

```
backend/           # FastAPI app + tests
frontend/          # Next.js admin portal
mobile/            # Flutter learner (CISSP Compass)
openapi/           # Shared OpenAPI artifact
assets/ui_images/  # Flutter three-platform mockups
docs/              # PRD + superpowers specs/plans
```

## Testing

```bash
cd backend && pytest
cd frontend && npm run test
cd mobile && dart test -p vm test/
```

## Documentation

- PRD: [`docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md`](docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md)
- Flutter design: [`docs/superpowers/specs/2026-08-10-flutter-learner-design.md`](docs/superpowers/specs/2026-08-10-flutter-learner-design.md)
- Agent guidance: [`CLAUDE.md`](CLAUDE.md)

## Disclaimer

This is an independent study aid. It is **not affiliated with, endorsed by, or a substitute
for** ISC2 or the official CISSP examination. CAT scoring is a simplified study estimate and
does not reflect official ISC2 scoring. CISSP® and ISC2® are registered trademarks of ISC2, Inc.
