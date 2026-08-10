# PRD Dual-Client Gap Closure Implementation Plan

> **For agentic workers:** Execute task-by-task. Steps use checkbox syntax.

**Goal:** Close PRD v1.3 MVP client gaps (Flutter learner + Next.js admin) and verify against §14.

**Design:** `docs/superpowers/specs/2026-08-10-prd-apps-gap-closure-design.md`

**Constraints:** No new backend routes. CAT language toggle never calls `/next`. Taxonomy names untranslated.

---

### Task 0: SDD sync

- [x] Gap design spec
- [x] This completion plan
- [x] Mark completed tasks in `2026-08-10-flutter-learner.md`

### Task 1: Practice book/chapter filters

- [x] Cascading Book/Chapter UI in `practice_screens.dart`
- [x] Pass `book_id` / `chapter_ids` on create
- [x] ARB strings en/zh

### Task 2: Explanations + markdown

- [x] Shared bilingual markdown / explanation panel
- [x] Practice post-submit: rationale + per-option + key points
- [x] Exam review bilingual content

### Task 3: CAT + auth tests

- [x] Wire `CatRunnerState` into CAT runner
- [x] Integration proof: toggle never hits `/next` (`cat_no_advance_integration_test.dart`)
- [x] Auth concurrent-refresh via `RefreshGate` unit tests

### Task 4: Analytics + keyboard + widgets

- [x] Trend / weak-areas / error-types / recommendation sections
- [x] Desktop keyboard shortcuts adapter (`runner_shortcuts.dart`)
- [x] Widget tests: bilingual, shell breakpoints (CI `flutter test`)

### Task 5: Admin gaps

- [x] Import template download
- [x] Field mapping UI (client-side CSV remap)
- [x] Language coverage panel on questions list
- [x] Class membership add/remove
- [x] Admin reset-password action

### Task 6: Verification

- [x] `flutter analyze` + `dart test -p vm` (unit suite)
- [x] `npm test` + lint/typecheck (frontend)
- [x] OpenAPI/Dart drift check script + CI
- [x] Docker smoke: health + admin login + book/chapter practice + CAT + coverage + no learner routes
- [x] §14 checklist below

## §14 acceptance mapping

| # | Owner | Status |
|---|---|---|
| 1–6 | Admin/ETL | Verified (template/mapping UI + ETL commit smoke) |
| 7 | Flutter practice filters | Done + API smoke with book/chapter |
| 8 | Flutter explanations | Done (panel + smoke `per_option`/`rationale`) |
| 9–13 | Existing Flutter | Smoke (CAT next OK; fixed needs full published bank) |
| 14 | Admin taxonomy | Existing |
| 15 | Flutter analytics | Done |
| 16–22 | Backend + client | Existing / CAT toggle tests |
| 23–24 | Admin editor + coverage | Coverage panel + filter |
| 25–31 | Dual client | Learner routes removed; shared API smoke |

## File map

```
docs/superpowers/specs/2026-08-10-prd-apps-gap-closure-design.md
docs/superpowers/plans/2026-08-10-prd-apps-gap-closure.md
mobile/lib/features/practice/practice_screens.dart
mobile/lib/features/exam/{exam_screens,cat_runner_state}.dart
mobile/lib/features/analytics/analytics_screen.dart
mobile/lib/design/{bilingual_text,runner_shortcuts}.dart
mobile/lib/core/refresh_gate.dart
mobile/test/*
frontend/src/features/import/import-wizard.tsx
frontend/src/features/admin/tabs.tsx
frontend/src/lib/import-template.ts
scripts/check_dart_api_drift.sh
```
