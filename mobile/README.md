# CISSP Compass — Flutter Learner Client

Cross-platform learner app (Android, iOS, Windows) for the CISSP Exam Practice System.
Shares the FastAPI backend with the Next.js **admin-only** portal.

## Prerequisites

- Flutter **3.32.8** stable (Dart 3.8+) — [install](https://docs.flutter.dev/get-started/install)
- Running backend (`docker compose up -d` from repo root, or local uvicorn on `:8000`)

## Run

```bash
cd mobile
flutter pub get
flutter gen-l10n

# Android emulator (maps host localhost → 10.0.2.2)
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000

# Windows desktop / iOS simulator (Mac)
flutter run --dart-define=API_BASE_URL=http://localhost:8000

# Physical device on LAN
flutter run --dart-define=API_BASE_URL=http://<host-lan-ip>:8000
```

Default login after seed: `admin@example.com` / `Adminadmin1` (dev only). Prefer registering a learner account for day-to-day use.

## Test

```bash
flutter analyze
# Pure unit tests (preferred on WSL — avoids flutter_tester WebSocket issues):
dart test -p vm test/
# Widget / golden updates (when adding screenshots):
flutter test --update-goldens
```

## Android release signing

Copy `android/key.properties.example` → `android/key.properties` and point `storeFile` at your upload keystore. Without it, release builds fall back to debug signing. See `docs/ops/production-runbook.md`.

## Dart API client drift

`packages/cissp_api` is hand-maintained against `openapi/openapi.json`. After backend OpenAPI changes:

1. Export: `cd backend && python -m app.scripts.export_openapi ../openapi/openapi.json`
2. Update Dart models/client in `packages/cissp_api` to match
3. Verify: `bash scripts/check_dart_api_drift.sh` from repo root

## Architecture

```
lib/core/       # config, Dio+auth, storage, errors
lib/design/     # theme, adaptive shell, Domain Compass, bilingual, legal
lib/features/   # auth, dashboard, analytics, practice, review, exam, settings
packages/cissp_api/  # hand-maintained OpenAPI mirrors
```

Auth: access token in memory; refresh token from `Set-Cookie`, persisted via secure storage, sent as body fallback on `/api/auth/refresh`.

Shared contract: [`../openapi/openapi.json`](../openapi/openapi.json).

Visual reference mockups: [`../assets/ui_images/`](../assets/ui_images/).

## Platform notes

| Target | Build host |
|--------|------------|
| Android | Linux/WSL/macOS/Windows + Android SDK |
| iOS | macOS + Xcode only |
| Windows | Windows host or `windows-latest` CI |

MVP excludes Flutter Web, macOS, and Linux desktop (PRD §12.2).
