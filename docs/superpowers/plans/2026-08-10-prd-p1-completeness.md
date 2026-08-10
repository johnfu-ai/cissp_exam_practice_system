# PRD P1 Completeness + E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land gap-closure, close P1 learner/admin gaps (ANS-05/06/08, PRAC-04/06, ETL-15, TAX bindings), add upload size limit + E2E, update docs, push to GitHub.

**Architecture:** Prefer existing APIs; small backend deltas (`weak_first`, `knowledge_point_id`, upload max bytes). Flutter practice runner gains metadata/related/questioned UI; admin taxonomy gains mappings + KP-domain panels. E2E is pytest acceptance + optional Docker smoke script.

**Tech Stack:** FastAPI, Flutter 3.32, Next.js 16, pytest, Vitest, Dio/`cissp_api`.

## Global Constraints

- CAT language toggle must never call `/next`.
- Do not translate taxonomy names (FR-I18N-05).
- No new OpenAPI endpoints except fields on existing schemas (`order_mode` enum, `knowledge_point_id`).
- TDD: write failing tests before production code for backend deltas.
- Do not commit secrets; exclude `mobile/android/build/`.

---

### Task 0: Commit gap-closure baseline

- [x] Stage gap-closure code + docs (exclude build artifacts)
- [x] Commit with message focused on closing §14 client gaps
- [x] Run `dart test -p vm test/` and `npm test` smoke if time allows

**Files:** existing WT from gap-closure plan; `docs/superpowers/{specs,plans}/2026-08-10-prd-apps-gap-closure*`

---

### Task 1: Backend `weak_first` + `knowledge_point_id` (TDD)

- [x] Add failing tests in `backend/tests/test_practice_api.py` (or service tests):
  - create session with `order_mode=weak_first` prefers previously wrong questions
  - create session with `knowledge_point_id` only returns mapped questions
- [x] Extend `OrderMode` + `SessionCreateIn.knowledge_point_id` in `backend/app/schemas/practice.py`
- [x] Implement filter + ordering in `backend/app/services/practice.py`
- [x] Export OpenAPI if schema changed: `python -m app.scripts.export_openapi ../openapi/openapi.json`
- [x] Regenerate Dart/TS clients if project scripts require it (or hand-update `cissp_api` models)

---

### Task 2: Upload size limit (NFR-SEC-08 partial, TDD)

- [x] Failing test: upload > max → 413
- [x] Settings `max_upload_bytes` (default 5_242_880)
- [x] Enforce in interactive import route / dependency
- [x] Pass tests

---

### Task 3: Flutter ANS-05/06/08 + PRAC-04/06

- [x] Practice create form: difficulty, question_type, tag dropdown; order includes `weak_first`; optional KP if tags/KPs APIs available
- [x] Post-submit panel: mapping labels + history list
- [x] `is_questioned` chip wired to state API
- [x] Related questions list via `relatedQuestions`
- [x] ARB en/zh strings + `flutter gen-l10n`
- [x] Unit/widget tests where seams exist

**Files:** `mobile/lib/features/practice/practice_screens.dart`, `mobile/lib/design/*`, `mobile/lib/l10n/*.arb`, `mobile/packages/cissp_api` if needed

---

### Task 4: Admin ETL mappings + KP domain bindings

- [x] API helpers in `frontend/src/lib/api/` if missing
- [x] UI: mappings CRUD panel (taxonomy page or import)
- [x] UI: KP ↔ domain bind/unbind on taxonomy KP tab
- [x] Vitest coverage for helpers / critical UI actions
- [x] Locale keys en/zh

**Files:** `frontend/src/features/taxonomy/*`, `frontend/src/lib/api/*`, `frontend/src/locales/{en,zh}.ts`

---

### Task 5: E2E acceptance

- [x] `backend/tests/test_e2e_acceptance.py` — practice/exam/CAT/analytics happy paths
- [x] `scripts/e2e_smoke.sh` — docker health + login + practice create
- [x] Document in README

---

### Task 6: README + artifacts + review + publish

- [x] Update root README (links, E2E, prod/backup, drift script)
- [x] Run backend pytest subset + frontend tests + flutter tests
- [x] Fix review findings
- [x] Commit P1 completeness
- [ ] `git push -u origin HEAD`
- [ ] Optionally `gh release` / tag — only if green

---

## File map

```
docs/superpowers/specs/2026-08-10-prd-p1-completeness-design.md
docs/superpowers/plans/2026-08-10-prd-p1-completeness.md
backend/app/schemas/practice.py
backend/app/services/practice.py
backend/app/core/config.py
backend/app/api/*import*
backend/tests/test_practice_api.py
backend/tests/test_e2e_acceptance.py
mobile/lib/features/practice/practice_screens.dart
mobile/lib/l10n/app_en.arb
mobile/lib/l10n/app_zh.arb
frontend/src/features/taxonomy/*
frontend/src/lib/api/*
frontend/src/locales/{en,zh}.ts
scripts/e2e_smoke.sh
README.md
openapi/openapi.json
```

## §14 / FR mapping (this wave)

| Item | Status target |
|---|---|
| Gap-closure §14 #7,#8,#15,#21 client | Committed |
| FR-ANS-05/06/08 | Flutter UI |
| FR-PRAC-04/06 | Flutter + small backend |
| FR-ETL-15 / TAX-04/05 UI | Admin |
| NFR-SEC-08 size | Backend |
| E2E | pytest + smoke script |
