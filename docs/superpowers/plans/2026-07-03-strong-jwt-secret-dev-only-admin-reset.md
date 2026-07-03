# P0 #2 — Strong JWT Secret + Dev-Only Admin Reset Implementation Plan

> TDD task-by-task. Spec: `docs/superpowers/specs/2026-07-03-strong-jwt-secret-dev-only-admin-reset-design.md`.

## Task 1: Settings JWT-secret validator (TDD)

**Files:** `backend/app/core/config.py`, `backend/tests/test_config.py` (new).

- [ ] Write failing tests (`test_config.py`): prod+weak raises (3 cases: change-me, dev-only-change-me, short); prod+strong OK; dev+default OK; "dev" env OK.
- [ ] Run → FAIL.
- [ ] Implement: add `from pydantic import model_validator` + `@model_validator(mode="after") _validate_jwt_secret` that raises when `app_env.lower()` not in {development,dev,test} and (`jwt_secret` in {change-me, dev-only-change-me} or `len < 32`).
- [ ] Run → pass. Commit `feat(security): reject weak JWT secret outside development`.

## Task 2: Dev-only admin reset in seed (TDD)

**Files:** `backend/app/db/seed.py`, `backend/tests/test_seed.py`.

- [ ] Write failing tests (append): dev+no-pw → admin password "admin"; prod+no-pw → random (not "admin"); prod+existing admin+explicit pw → reset; prod+existing admin+no pw → no reset; dev+existing admin+explicit pw → reset. Patch `app.db.seed.settings` with a constructed `Settings` for prod/dev cases.
- [ ] Run → FAIL.
- [ ] Implement: `dev_mode = settings.app_env.lower() in {"development","dev","test"}`; `effective_pw = settings.seed_admin_password or ("admin" if dev_mode else None)`; creation uses `effective_pw or secrets.token_urlsafe(16)`; existing-admin reset only when `effective_pw is not None`; print dev warning when using the "admin" default, print generated password only when `effective_pw is None`.
- [ ] Run full seed suite → pass. Commit `feat(security): gate admin password reset behind dev mode (dev default admin/admin)`.

## Task 3: Compose + docs

**Files:** `docker-compose.yml`, `CLAUDE.md`.

- [ ] Remove `SEED_ADMIN_PASSWORD: admin` from `docker-compose.yml`.
- [ ] Update CLAUDE.md P0 #2 note (dev-only reset; validator; compose change).
- [ ] Full backend suite green. Commit `chore(security): remove hardcoded admin password from dev compose`.
- [ ] Push.
