# Flutter Learner Client Design (PRD v1.3)

Date: 2026-08-10
Status: Approved
Related PRD: v1.3 (§6.13 FR-CLIENT, §8.1, §9.2.1, §12.1)
Visual reference: `assets/ui_images/flutter-ui-01..16-*-3platform.png`

## 1. Goals and scope

Build one Dart/Flutter learner app covering Android, iOS, and Windows against the existing FastAPI backend. Next.js becomes an admin-only portal (import, questions, taxonomy, admin, account settings).

### In scope (Flutter)

- Auth: register, login, logout, forgot/reset password, change password, session restore
- Dashboard + analytics
- Practice create/runner/summary + review (wrong/bookmarked/needs_review)
- Fixed exam + CAT exam (setup, runner, report, review, history)
- Settings: interface language (en/zh) + question content language (en/zh/bilingual)
- Adaptive phone/desktop shells, legal footer, bilingual question rendering

### Out of scope (Flutter)

- Admin, ETL import, question editor, taxonomy writes
- Flutter Web / macOS / Linux (PRD §12.2)
- Offline sync, dark mode (P2), complex item types

### Next.js transition

After Flutter parity tests pass, remove learner routes from Next.js. Web portal keeps: login/register/forgot-password, settings, import, questions, taxonomy, admin. Users without management permissions see an admin-access-required screen.

## 2. Architecture

```text
mobile/
  lib/
    core/          # config, auth session, Dio transport, storage, errors, i18n bootstrap
    design/        # tokens, adaptive shell, Domain Compass, bilingual text, legal footer
    features/      # auth, dashboard, analytics, practice, review, exam, settings
  packages/cissp_api/  # generated OpenAPI Dart/Dio client
  test/
openapi/openapi.json   # single shared contract (FastAPI → TS + Dart)
```

Deep modules:

| Module | Interface | Hides |
|---|---|---|
| `AuthSession` | login/register/refresh/logout/me | cookie parse, secure storage, 401 singleton |
| `ApiClient` | typed GET/POST helpers | Dio interceptors, error mapping |
| `PracticeRunnerMachine` | pure selection/submit transitions | UI |
| `ExamControllers` | fixed vs CAT delivery/answer/finish | route differences |
| `LocaleController` | interface + content language | ARB + preference sync |

Server remains source of truth for session progress. Client caches only UI prefs and active-session IDs for resume.

## 3. Contract and auth

- Relocate `frontend/openapi.json` → `openapi/openapi.json`.
- Frontend `gen:api` and CI drift checks consume the shared file.
- Generate `mobile/packages/cissp_api` from the same artifact.
- Access token: memory only (optional short resume cache).
- Refresh token: parse `Set-Cookie: refresh_token=...` from login/register/refresh; persist via `flutter_secure_storage`; send body fallback on `/api/auth/refresh` and `/logout`.
- Concurrent 401s share one refresh; failure clears session and routes to login.
- Config: `--dart-define=API_BASE_URL=...` (Android emulator default `http://10.0.2.2:8000`).

## 4. Visual system

Brand: **CISSP Compass**. Palette aligned with existing product:

| Token | Hex | Role |
|---|---|---|
| primary | `#007AFF` | actions, selection |
| canvas | `#F7F7FA` | app background |
| card | `#FFFFFF` | elevated surfaces |
| success | `#34C759` | correct / ready |
| warning | `#FF9500` | medium mastery |
| destructive | `#FF3B30` | wrong / logout |
| muted | `#8E8E93` | secondary labels |

Signature element: eight-segment **Domain Compass** (custom painter). Quiet cards, 12px radius, light mode only. Mobile: bottom nav (Home / Practice / Exam / Review / Settings). Desktop: left sidebar + optional right detail/palette panes + keyboard shortcuts.

Mockups are visual references, not embedded assets.

## 5. Localization

Two independent axes:

1. `interface_language` (`en`/`zh`) → ARB/`AppLocalizations`
2. `language_mode` (`en`/`zh`/`bilingual`) → question rendering only

First frame: read cached `interface_language` before `runApp`, then reconcile with `/api/users/me/preferences`. In-runner content toggles are pure local state and must never call `/next` or submit (CAT invariant). Taxonomy names are never translated (FR-I18N-05). Legal disclaimer on every shell (NFR-COMP-03/04).

## 6. Feature contracts (mirror Next.js)

### Practice

- Create via `POST /api/practice/sessions` with scope filters.
- Deliver by position: `GET .../questions/{pos}` (not `/next`).
- One answer per question (409 on re-answer); pause/resume; finish → summary.
- Option shuffle is client-side display only; submit uses canonical `order_index`.
- Post-submit: state updates via `PUT /api/practice/questions/{id}/state`.

### Fixed exam

- `POST /api/exam/sessions` `{kind:"fixed"}`; positional delivery; revisable upsert answers; deadline auto-submit; palette navigation.

### CAT exam

- `POST /api/exam/sessions` `{kind:"cat"}`; `GET .../next`; forward-only; wrong-position 422; language toggle never advances; report surfaces ability/CI/SEM/readiness + `DISCLAIMER`.

### Analytics

- `/api/analytics/{dashboard,domains,trend,weak-areas,error-types,recommendation}` gated by `practice:read`.

## 7. Testing

- Unit: runner machine, session payload, trackers, format helpers, locale resolution, CAT no-advance.
- Widget: login, settings language cards, bilingual text, adaptive shell breakpoints.
- Golden: phone + Windows widths for key screens.
- Repository: Dio mocks for auth refresh concurrency and error mapping.
- Smoke: real backend login → preferences → practice → fixed → CAT.
- CI: analyze/test on Linux; Android APK on Ubuntu; Windows build on `windows-latest`; unsigned iOS on `macos-latest`.

## 8. Acceptance

1. One Flutter codebase builds Android, iOS, Windows.
2. Learner can complete auth, practice, review, fixed exam, CAT, analytics, settings.
3. Content language toggle never advances CAT.
4. Interface language switches chrome instantly and persists.
5. Next.js no longer exposes learner navigation/routes.
6. Flutter and Next.js share `openapi/openapi.json` with CI drift checks.
7. Legal footer + CAT disclaimer present.
