# Flutter Learner MVP Implementation Plan

> **For agentic workers:** Execute task-by-task. Steps use checkbox syntax.

**Goal:** Ship a Flutter learner client (Android/iOS/Windows) against the existing FastAPI APIs, then retire Next.js learner routes so the web app is admin-only.

**Architecture:** See `docs/superpowers/specs/2026-08-10-flutter-learner-design.md`. Shared OpenAPI at `openapi/openapi.json`. Deep modules in `mobile/lib/{core,design,features}`.

**Tech Stack:** Flutter stable, Riverpod, GoRouter, Dio, flutter_secure_storage, shared_preferences, flutter_localizations + ARB, flutter_markdown; FastAPI/Next.js unchanged except OpenAPI path + admin-only frontend.

## Global constraints

- Do not invent new backend routes; use implemented paths (`/api/exam`, practice positional delivery, analytics `/dashboard`).
- Access token in memory; refresh from Set-Cookie + body fallback; no backend auth change.
- CAT language toggle must never call `/next`.
- Taxonomy names untranslated; question content via FR-LANG.
- Light mode only. No Flutter Web/macOS/Linux in MVP.
- Keep Next.js learner code until Flutter parity tests pass, then remove.

---

### Task 1: Scaffold mobile project + docs (done in this plan commit set)

- [ ] Create `mobile/` via `flutter create --platforms=android,ios,windows`
- [ ] Add `pubspec.yaml` deps: flutter_riverpod, go_router, dio, flutter_secure_storage, shared_preferences, flutter_markdown, intl, freezed/json_serializable as needed
- [ ] Layout `lib/core`, `lib/design`, `lib/features`
- [ ] Pin Flutter via `.fvmrc` or README version note
- [ ] Update root `.gitignore` for Flutter artifacts

### Task 2: Shared OpenAPI + Dart client

- [ ] Move `frontend/openapi.json` → `openapi/openapi.json`
- [ ] Update frontend `package.json` `gen:api` and CI paths
- [ ] Generate `mobile/packages/cissp_api` (hand-written thin client mirroring OpenAPI if generator tooling unavailable; prefer openapi-generator dart-dio when available)
- [ ] CI drift: export OpenAPI + regenerate Dart/TS checks

### Task 3: Auth transport

- [ ] `ApiConfig` from `--dart-define=API_BASE_URL`
- [ ] `AuthSession` + Dio interceptor (Bearer, refresh singleton, cookie parse)
- [ ] Secure storage adapter + in-memory test adapter
- [ ] Unit tests for concurrent 401 refresh and logout

### Task 4: Design system + shell + i18n

- [ ] Design tokens + ThemeData
- [ ] `AdaptiveScaffold` (bottom nav / sidebar)
- [ ] `DomainCompass`, `BilingualText`, `LegalFooter`, `Eyebrow`, option list
- [ ] ARB en/zh; bootstrap locale from cache then server
- [ ] Widget tests for shell breakpoints + bilingual fallback

### Task 5: Auth + dashboard + analytics + settings screens

- [ ] Login / register / forgot-password flows
- [ ] Dashboard + analytics views over `/api/analytics/*`
- [ ] Settings: interface + content language cards, change password
- [ ] Tests: settings cards, locale persistence

### Task 6: Practice + review

- [ ] Pure `PracticeRunnerMachine` (port from Next.js)
- [ ] Create session form, runner, summary, resume tracker
- [ ] Review subset launchers
- [ ] Tests: machine transitions, shuffle preserves order_index, CAT-like toggle isolation for language

### Task 7: Fixed + CAT exams

- [ ] Fixed runner with timer + palette + revisable answers
- [ ] CAT runner with `/next`, disclaimer, forward-only
- [ ] Report / review / history
- [ ] Critical test: language toggle never advances CAT

### Task 8: Next.js admin-only

- [ ] Remove learner route pages and unused feature modules
- [ ] Sidebar: manage links only; no dashboard/practice/exam/review/analytics
- [ ] Root redirect: authed → first available admin route or access-required page
- [ ] Keep settings + auth for admins
- [ ] Frontend tests green

### Task 9: CI + docs + verification

- [ ] GitHub Actions Flutter jobs
- [ ] README + CLAUDE.md mobile section
- [ ] Full verification: backend pytest, frontend vitest/build, flutter analyze/test, docker health

## File map (create)

```
docs/superpowers/specs/2026-08-10-flutter-learner-design.md
docs/superpowers/plans/2026-08-10-flutter-learner.md
openapi/openapi.json
mobile/
  pubspec.yaml
  lib/main.dart
  lib/core/{config,api,auth,storage,errors,i18n}.dart
  lib/design/{theme,shell,compass,bilingual,legal}.dart
  lib/features/{auth,dashboard,analytics,practice,review,exam,settings}/
  packages/cissp_api/
  test/
```

## Acceptance checklist

Matches PRD §14 items 7–13, 18–22, 25–31 and FR-CLIENT-01..06.
