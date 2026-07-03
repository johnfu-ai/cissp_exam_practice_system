# P0 #3 — Cross-Tenant IDOR Implementation Plan

> TDD task-by-task. Spec: `docs/superpowers/specs/2026-07-03-cross-tenant-idor-question-etl-design.md`.

## Task 1: Question service org-gate (TDD)

**Files:** `backend/app/services/question.py`, `backend/tests/test_question_service.py`.

- [ ] Write failing tests: `get_question` raises `NotFound` when `org_id` mismatches; `update_question`/`delete_question`/`submit_review`/`create_feedback` raise `NotFound` for cross-org question_id; same-org succeeds. (Use the existing `session_with_roles` + two-org helper pattern.)
- [ ] Run → FAIL.
- [ ] Implement: `get_question(session, question_id, *, org_id)` (verify `organization_id`); thread `org_id` through `update_question`/`delete_question`/`submit_review`/`create_feedback`.
- [ ] Run → pass. Commit `feat(question): org-scope get_question + thread org_id through mutations`.

## Task 2: Question API org-threading (TDD)

**Files:** `backend/app/api/questions.py`, `backend/tests/test_question_api.py`.

- [ ] Write failing tests: cross-org GET/PUT/DELETE/review/revisions/feedback → 404; same-org → 200. Add the `GET /{id}/feedback` ownership gate.
- [ ] Run → FAIL.
- [ ] Implement: capture `current` (not `_`) on read routes; pass `org_id=current.org_id` to every `svc.*` call; add `get_question` gate to `list_feedback`.
- [ ] Run → pass; full suite green. Commit `feat(question): close cross-tenant IDOR on {question_id} routes`.

## Task 3: ETL run org-gate (TDD)

**Files:** `backend/app/etl/runner.py`, `backend/app/api/etl.py`, `backend/tests/etl/test_api_etl.py` (+ `test_runner.py` if present).

- [ ] Write failing tests: cross-org get_run/commit_run/rollback_run → 404; missing run → 404; wrong-phase → 409 (unchanged); same-org → 200.
- [ ] Run → FAIL.
- [ ] Implement: `run_commit`/`run_rollback` raise `LookupError` for missing/cross-org; `get_run`/`commit_run`/`rollback_run` routes thread `current.org_id` + catch `LookupError` → 404.
- [ ] Run → pass; full suite green. Commit `feat(etl): close cross-tenant IDOR on run get/commit/rollback`.

## Task 4: Docs + push

- [ ] Update CLAUDE.md + audit doc (P0 #3 DONE). Full suite + drift green. Commit + push.
