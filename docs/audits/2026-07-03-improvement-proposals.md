# CISSP Exam System — Improvement Proposals

**Date:** 2026-07-03
**Method:** Deep study of the codebase across six subsystem audits (security & auth, backend service/data layer, testing & migrations, frontend, DevOps/production-readiness, PRD/NFR compliance). Every finding below is cited to real `file:line` references verified against the current `master` tree.

---

## Executive summary

This is a genuinely well-engineered project: the full PRD functional scope is implemented (104 endpoints, 435 backend + 87 frontend tests, zero migration drift, real-PostgreSQL test isolation, clean service-layer separation, snapshots for historical integrity, a rule-driven CAT engine with honest disclaimers). The architecture is sound and the code is readable.

**The gaps cluster in three areas, not in feature completeness:**

1. **Security hardening** — several remotely-exploitable issues exist in the default deployment (unauthenticated password reset, forgeable JWT secret, cross-tenant IDOR, no XSS sanitization).
2. **Production / operational maturity** — no CI, no observability, no backups, no TLS path, single-worker deployments, secrets in plaintext compose.
3. **PRD compliance details** — a handful of explicitly-required items are missing or simplified (CSV/XLSX upload, keyboard a11y, legal disclaimers, three-level dedup, CAT difficulty variation, per-option explanations).

Severities below are calibrated to *a real deployment* — many items are acceptable for local dev but block any non-local use.

---

## P0 — Critical (fix before any non-local deployment)

> **Status:** P0 #1 ✅ **DONE (2026-07-03)** — see `docs/superpowers/specs/2026-07-03-secure-password-reset-design.md` + `docs/superpowers/plans/2026-07-03-secure-password-reset.md`. Old unauth `POST /api/auth/reset-password` removed; replaced with `PUT /api/auth/password` (authenticated, current-password), `POST /api/auth/reset-password/{request,confirm}` (single-use Redis token, 15-min TTL, no enumeration), and admin `POST /api/admin/users/{id}/reset-password`. New `AuditAction.password_reset`/`password_change` (migration `e7a1b2c3d4e5`). 460 backend + 90 frontend tests, zero drift. Items #2–#6 below remain open.
>
> **P0 #2 ✅ DONE (2026-07-03)** — see `docs/superpowers/specs/2026-07-03-strong-jwt-secret-dev-only-admin-reset-design.md` + `docs/superpowers/plans/2026-07-03-strong-jwt-secret-dev-only-admin-reset.md`. `Settings` validator rejects default/short `jwt_secret` outside dev/test; `seed.py` gates admin password reset behind dev mode (dev defaults to `admin`; prod never resets + generates random); `docker-compose.yml` no longer hardcodes `SEED_ADMIN_PASSWORD`. 472 backend tests, zero drift. Items #3–#6 remain open.
>
> **P0 #3 ✅ DONE (2026-07-03)** — see `docs/superpowers/specs/2026-07-03-cross-tenant-idor-question-etl-design.md` + `docs/superpowers/plans/2026-07-03-cross-tenant-idor-question-etl.md`. `get_question()` requires `org_id` (NotFound on cross-org); all `{question_id}` routes thread `current.org_id` (added the missing gate on `GET /{id}/feedback`); `run_commit`/`run_rollback`/`get_run` verify `run.organization_id` (cross-org → 404). 480 backend tests, zero drift. Items #4–#6 remain open.
>
> **P0 #4 ✅ DONE (2026-07-04)** — see `docs/superpowers/specs/2026-07-04-xss-sanitization-csp-design.md` + `docs/superpowers/plans/2026-07-04-xss-sanitization-csp.md`. `nh3`-based `sanitize_rich_text` applied on all API + ETL rich-text writes (Pydantic validators on `TranslationIn`/`TranslationOptionIn`/`FeedbackIn`; ETL `_translation_payload`); `SecurityHeadersMiddleware` adds strict CSP + `X-Content-Type-Options`/`X-Frame-Options`/`Referrer-Policy` (HSTS over TLS only). NFR-SEC-07. 490 backend tests, zero drift. Items #5–#6 remain open.
>
> **P0 #5 ✅ DONE (2026-07-04)** — `<LegalFooter>` (role=contentinfo) in both the `(app)` and `(auth)` layouts renders the trademark attribution + "not an official ISC2 platform" disclaimer on every page (locale keys en/zh). NFR-COMP-03/04. 93 frontend tests, lint 0, build green. Item #6 remains open.
>
> **P0 #6 ✅ DONE (2026-07-04)** — see `docs/superpowers/specs/2026-07-04-health-tls-migrations-design.md` + `docs/superpowers/plans/2026-07-04-health-tls-migrations.md`. `/live` (liveness, 200) + `/ready`/`/health` (503 when DB/Redis down — fixes always-200); shared Redis probe client; `HTTPSRedirectMiddleware` in non-dev; one-shot `migrate` compose service (backend `depends_on: service_completed_successfully`) + backend `/live` healthcheck. E2e stack-verified (migrate exit 0, backend healthy, login + reset + CSP all green). Also caught+fixed a P0 #1 bug: reset `request` now returns the token for any dev env (`dev`/`development`/`test`). 496 backend tests, zero drift.
>
> **All P0 items (#1–#6) are DONE.** Branch `fix/p0-security-hardening` pushed to `origin`.

| # | Proposal | Where | Why it's critical |
|---|----------|-------|-------------------|
| 1 | **Replace unauthenticated `/reset-password` with a token-based flow.** The endpoint takes `{email, new_password}` with no old password, no email token, no auth — anyone who knows an email takes over the account. The admin email is public in `docker-compose.yml`. | `backend/app/api/auth.py:113-129`; only happy-path tested at `backend/tests/test_auth_api.py:72` | One-request account takeover, including `system_admin`. |
| 2 | **Enforce a strong JWT secret + stop shipping `admin/admin`.** `jwt_secret` defaults to `change-me` / `dev-only-change-me` with no startup validation; `SEED_ADMIN_PASSWORD: admin` in compose; `seed.py:161-167` *forcibly resets* the admin password to `admin` on every restart, defeating rotation. | `backend/app/core/config.py:10`, `docker-compose.yml:34,38`, `backend/app/db/seed.py:161-167` | Knowing the secret ⇒ forge any token as any role/org. Known admin creds ⇒ trivial login. |
| 3 | **Add org-scoping to all `{question_id}` and `{run_id}` routes (cross-tenant IDOR).** `get_question()` fetches by PK with no `organization_id` filter, so a user in org A can read/edit/delete/publish/view-revisions/post-feedback on any org's question by UUID. Same pattern on ETL `get_run`/`commit`/`rollback`. | `backend/app/services/question.py:258-263` (root cause); `backend/app/api/questions.py:208-326`; `backend/app/api/etl.py:60-89`; `backend/app/etl/runner.py:90-132` | Cross-tenant leak of stems, answer keys, revision snapshots + destructive cross-org edits. `list_questions` *is* scoped, which masks the gap. |
| 4 | **Sanitize rich-text content (XSS) + add CSP.** Question stems/options/explanations are stored as markdown with no sanitization library and no `Content-Security-Policy`. Frontend stores tokens in `sessionStorage`, so a single stored XSS exfiltrates live tokens. | `backend/requirements.txt` (no bleach/nh3); `backend/app/etl/load.py:135`; `backend/app/main.py:22-28` (no CSP); `frontend/src/lib/auth-store.ts:34-35` | PRD §7.2 NFR-SEC-07 explicitly requires XSS allowlist filtering. |
| 5 | **Add the required legal disclaimers.** No trademark notice ("CISSP and ISC2 are registered trademarks of ISC2, Inc.") and no site-wide "this is not an official ISC2 platform" statement exist anywhere in the frontend — only CAT-specific scoring disclaimers are present. | missing from all `frontend/src/`; PRD §7.5 lines 417-418 | Legal/compliance exposure; the product uses "CISSP"/"ISC2" throughout. |
| 6 | **Make `/health` a real readiness probe + add TLS + run migrations safely.** `/health` swallows all exceptions and returns HTTP 200 even when DB/Redis are down (useless for k8s readiness). No reverse proxy/TLS exists. `alembic upgrade head` runs in-container on every start with no lock — races across N replicas. | `backend/app/main.py:30-47`; `docker-compose.yml` (no proxy, published ports); `backend/Dockerfile:22` | A sick pod stays in rotation; all traffic is cleartext; concurrent rollouts corrupt migration history. |

---

## P1 — High

### Auth & session security

| # | Proposal | Where |
|---|----------|-------|
| 7 | **Refresh-token reuse detection + family invalidation.** Rotation deletes the old token with no family/id — a stolen+rotated token is undetectable. Add `family_id` + `rotated_from`; on reuse, revoke the whole family. | `backend/app/core/security.py:106-110`; `backend/app/services/auth.py:198-215` |
| 8 | **Make access tokens revocable; reject disabled users.** `jti` is generated but never stored/checked — logout doesn't kill the access token (valid up to 60 min). `get_current_user` doesn't check `user.status`, and perms are trusted from the token (stale up to 60 min after a role revocation). | `backend/app/core/security.py:38`; `backend/app/dependencies.py:63-86` |
| 9 | **Move refresh token to an httpOnly cookie; fix the concurrent-401 refresh race.** Both tokens live in `sessionStorage` (XSS-exfiltrable). Parallel 401s each fire `/refresh` — one wins, the rest `clear()` and log the user out. Add a singleton refresh promise. | `frontend/src/lib/auth-store.ts:34-35`; `frontend/src/lib/api.ts:12-38` |
| 10 | **Add per-IP rate limiting + fix the login timing/enumeration oracles.** Only per-email lockout exists (account-DoS vector; password-spray never trips it). Login short-circuits on missing user (timing oracle); `/reset-password` returns 404-vs-200 (enumeration). | `backend/app/services/auth.py:53-91,178`; `backend/app/api/auth.py:119-122` |
| 11 | **Strengthen password policy; drop unmaintained `passlib`.** Policy is length-8 only (no breach-list/complexity). `passlib 1.7.4` is unmaintained (Oct 2020) and emits deprecation warnings against bcrypt 4.x — call `bcrypt` directly. | `backend/app/schemas/auth.py:8`; `backend/requirements.txt:11` |

### Backend performance & correctness

| # | Proposal | Where |
|---|----------|-------|
| 12 | **Add indexes on FK columns.** Only the GIN index on `available_languages` exists. Critical gaps: `question_mappings(domain_id/question_id)`, `practice_answers(session_id)`, `exam_answers(session_id)`, `audit_logs(organization_id, occurred_at)`, `exam_sessions(user_id, status)`. Single highest-impact perf change. | `backend/app/alembic/versions/66bec070d8fc_initial_schema.py` (all tables) |
| 13 | **Fix N+1 queries in the hot paths.** Question list calls `_mappings_out` per item (101 queries/page); exam review does `session.get(Question)` + answer query per item (300+ queries for a 150-item exam); practice summary loads mappings+domains per answer; analytics `personal_report` calls `_answer_rows` ~7× and scans the **entire** `question_mappings` table per request. | `backend/app/api/questions.py:144-154`; `backend/app/services/exam.py:863-955`; `backend/app/services/practice.py:441-503`; `backend/app/services/analytics.py:407,431-442` |
| 14 | **Paginate unbounded list endpoints.** `/api/exam/history`, `/api/questions/{id}/revisions`, `/api/questions/{id}/feedback`, `/admin/classes/{id}/members`, and practice `_history_out` (returns *all* past answers inline) have no LIMIT/OFFSET. | `backend/app/api/exam.py:186`; `backend/app/api/questions.py:282-326`; `backend/app/api/admin.py:211`; `backend/app/services/practice.py:300-317` |
| 15 | **Serialize CAT/practice answer submits.** The forward-only invariant relies on a Python position check with no `SELECT … FOR UPDATE` and no unique constraint on `(session_id, question_id)` — two concurrent submits double-insert and corrupt `position`/`seen`. | `backend/app/services/exam.py:534-654`; `backend/app/services/practice.py:332-339` |
| 16 | **Restore CAT difficulty variation + make `update_ability` use it.** ETL hardcodes `difficulty=3` for every question (`transform.py:108`; `RawQuestion` has no difficulty field), and `cat_engine.update_ability` accepts `difficulty` but never reads it. With uniform difficulty, "ability-matched selection" (§11.1 items 1+4, FR-CAT-05) is effectively meaningless. | `backend/app/etl/transform.py:108`; `backend/app/services/cat_engine.py:57-62` |
| 17 | **Implement the missing two dedup levels.** PRD §10.4 rule 6 / FR-ETL-08 require *three-level* dedup (external ID + stem hash + option fingerprint); only external-ID dedup is implemented. | `backend/app/etl/load.py:100-106` |
| 18 | **Populate per-option explanations + read `option_explanations`/`difficulty`/`license` from source.** FR-ANS-04 data model supports per-option explanations but ETL writes `None`; `difficulty` and `license_status` are hardcoded rather than read from source. | `backend/app/etl/load.py:142,230`; `backend/app/etl/transform.py:108` |
| 19 | **Enforce partial-zh 1:1 option pairing (§10.2 rule 8) and empty-stem/explanation publish blocking (rule 6).** CLAUDE.md calls partial-zh a "non-blocking follow-up," but it's an explicit PRD requirement. Empty stem/explanation never blocks publish. | `backend/app/etl/transform.py:49-80` |

### Testing & CI

| # | Proposal | Where |
|---|----------|-------|
| 20 | **Add a CI pipeline.** No `.github/workflows`, no Makefile — 435+87 tests + the no-drift guard run only locally. The drift guard is the single highest-value gate and isn't enforced anywhere. | repo root |
| 21 | **Make conftest not require CREATEDB.** Per-test DB setup hard-requires createdb privilege, so the container/CI test-runner fails (the `cissp` user lacks it). Fall back to a pre-created DB + `TRUNCATE … CASCADE`, or grant createdb. Blocks #20. | `backend/tests/conftest.py:24-29` |
| 22 | **Add real downgrade + drift-meta tests.** The only downgrade test runs on an empty DB (asserts nothing). The `a1b2c3d4e5f6` bilingual-merge downgrade is lossy and untested — the highest-stakes migration has a dark reverse path. Add a test-of-the-test that the drift guard actually catches a real model change. | `backend/tests/test_migrations.py:44-63`; `backend/app/alembic/versions/a1b2c3d4e5f6_question_translations.py:208-243` |
| 23 | **Add concurrency + N+1 query-count tests; configure coverage.** No tests assert the CAT race is safe, no tests bound query counts (an N+1 regression passes green), no `pytest-cov`/threshold. Also: switch the 5 single-router API tests to `create_app()` (the stale `Explanation` import excuse is gone). | `backend/tests/` (none); `backend/pytest.ini` |

### DevOps

| # | Proposal | Where |
|---|----------|-------|
| 24 | **Run multiple uvicorn workers; add graceful shutdown.** Single sync worker + bcrypt-on-event-loop = no prod concurrency. No lifespan/SIGTERM handling — in-flight exam submissions are killed on deploy. | `backend/Dockerfile:22` |
| 25 | **Add backups + Redis durability.** Postgres is on a named volume with no `pg_dump`/cron/restore tested; Redis has no volume and no persistence — a restart logs out every user and resets all lockouts (undocumented). PRD §7.3 requires daily user-data backup. | `docker-compose.yml:10-11,18-26` |
| 26 | **Add observability.** No structured logging, no request IDs, no metrics, no Sentry. Default uvicorn access logs only. | `backend/app/main.py` |
| 27 | **Harden Dockerfiles.** Both run as root; neither is multi-stage (gcc/libpq-dev and node_modules ship in the final image); minimal `.dockerignore`; npmmirror.com hardcoded in frontend build. | `backend/Dockerfile`; `frontend/Dockerfile:9-18` |
| 28 | **Add resource limits + restart policies + prod/dev compose split.** No mem/cpu limits, no `restart:`, one compose file for dev and "prod." | `docker-compose.yml` |

### Frontend

| # | Proposal | Where |
|---|----------|-------|
| 29 | **Add error boundaries + 401 redirect.** No `error.tsx`/`global-error.tsx` — a bad API shape renders a blank screen. After refresh failure, `clear()` runs but the user stays stranded on a protected page (every fetch 401s). | `frontend/src/app/` (none); `frontend/src/lib/api.ts:28-31` |
| 30 | **Handle errors in auth forms.** Login has `try/finally` with no `catch` (network errors = unhandled rejection, no feedback); register sets the raw backend JSON body as the error message and has no busy state. | `frontend/src/app/(auth)/login/page.tsx:29-51`; `register/page.tsx:23-39` |
| 31 | **Invalidate React Query caches on mutations.** Create/update/delete/review-question don't invalidate the list cache (stale list view); `useUpdateQuestionState` doesn't invalidate analytics/review queries. | `frontend/src/lib/api/questions.ts:42-75`; `frontend/src/lib/api/practice.ts:94-102` |
| 32 | **Generate API types from OpenAPI.** 710 lines of hand-written types "mirroring" Pydantic schemas will silently drift (e.g. `ExamSession.status: string` should be `SessionStatus`). Use `openapi-typescript` against `/openapi.json` + a CI drift check. | `frontend/src/lib/api/types.ts:1` |
| 33 | **Fix i18n bypass + parity test.** Two duplicate `labelize` functions Title-Case raw enum values in English, bypassing `t()` in the practice runner + create form (zh users see English). The parity test is one-directional and doesn't check non-empty/differing zh values. | `frontend/src/features/practice/runner.tsx:67`; `create-session-form.tsx:45`; `frontend/src/locales/__tests__/i18n.test.ts:7-10` |
| 34 | **Add keyboard answer selection/submission (P0 a11y) + fix WCAG contrast.** No `onKeyDown` handlers in any runner (PRD §7.4 NFR-UX-04 is P0). `--success` (#34C759) and `--destructive` (#FF3B30) on white fail AA 4.5:1. | `frontend/src/features/{practice,exam}/`; `frontend/src/app/globals.css:13,21,23` |

### PRD scope gaps (verify intent)

| # | Proposal | Where |
|---|----------|-------|
| 35 | **Decide on CSV/XLSX/JSON file upload (FR-IMP-01, §12.1 MVP item 2, §14.1).** CLAUDE.md frames the JSONL-only pipeline as intentional, but the PRD lists CSV/XLSX/JSON import as an MVP *must-include* and an acceptance criterion. This is a genuine scope decision, not a bug — confirm with the PRD owner whether the JSONL dataset flow satisfies the intent or a real upload endpoint is required. | `backend/app/etl/extract.py` (only `DatasetReader`); PRD §9.6 lists 4 extractors |
| 36 | **Add the missing UI affordances: forgot-password page, practice timer display, practice option shuffling, same-KP recommendation, notes CRUD.** FR-ANS-07/08, FR-PRAC-09, §8.1. Backend tracks practice `elapsed_ms` but the runner never displays it. | `frontend/src/app/(auth)/` (no forgot-password); `frontend/src/features/practice/runner.tsx` |

---

## P2 — Medium (curated)

- **Centralize transaction management** in `get_session` (commit-on-success / rollback-on-error); today only `admin.py` rolls back explicitly (`backend/app/dependencies.py`, `get_session`).
- **Unify the duplicated service exception hierarchy** (`ValidationError`/`NotFound`/`ConflictError` redefined in 5 modules) into `app/services/errors.py`.
- **Split `ExamSession.config` JSONB** into client-visible + internal columns so the trust boundary is structural, not an output allowlist (`_INTERNAL_CONFIG_KEYS`).
- **Cache the CAT candidate pool** (re-fetched on every one of up to 150 answers) and deepen anti-cluster memory beyond 1 item.
- **Fix `language_filter` bilingual** to use one GIN-indexed `contains(["en","zh"])` instead of two `.any()` scans; show a CAT item-count *range* not a misleading `total: 150`.
- **Tune the DB pool** (`pool_size`/`max_overflow`/`pool_recycle=1800`); add DB/Redis SSL for remote deployments.
- **Move analytics aggregation to SQL** (the in-Python merge of practice+exam answers is the main scale risk for NFR-PERF-06/07).
- **Frontend polish:** use `<Link>` not `<a>` on auth pages; `router.replace` not `window.location.replace` on exam finish; `AlertDialog` not `window.confirm` for destructive admin actions; retry path for auto-submit failure; rollback optimistic locale switch on settings failure; add `typecheck` script + stricter `tsconfig` (`noUnusedLocals`, `noUncheckedIndexedAccess`).
- **Admin `report_summary`** loads all answer rows + all sessions into Python — replace with SQL aggregation (`func.count`, `func.sum`, `JSONB_ARRAY_ELEMENTS_TEXT`).
- **Restrict CORS** methods/headers; add a startup guard against `cors_origins="*"` with credentials.

---

## P3 — Low / polish (brief)

Snapshot omits `source`/`license_status`/`prompt_items`; cycle detection could use a recursive CTE; dead `darkMode:"class"` config; dead code in `resume-panel.tsx`; duplicated `labelize`/`langBadge`/jsdom polyfills; `renderWithProviders` doesn't wrap a Router; login/register pages aren't thin wrappers (violate the `features/` convention); inconsistent ENUM DROP TYPE styles in migrations; `text_format` shared-enum drop ordering fragile; Redis new-connection-per-health-probe; `.dockerignore` ships tests/docs to the image; no transitive lockfile (`pip-tools`/`uv`); `alembic.ini` logging minimal.

---

## Recommended order

1. **Quick security wins (days):** #1 (reset-password), #2 (JWT secret + admin), #3 (IDOR scoping), #5 (disclaimers) — all small, high-impact, mostly mechanical.
2. **Unblock CI (days):** #20 + #21 — once tests run in CI, everything else gets safer to fix.
3. **Prod-readiness baseline (week):** #6 (health/TLS/migrations), #24–28 (workers, backups, observability, Dockerfiles, limits).
4. **Auth hardening (week):** #7–11 (refresh reuse, revocation, cookie storage, rate limiting, passlib).
5. **Performance (week):** #12–14 (indexes, N+1, pagination) — biggest bang/buck.
6. **Correctness & PRD gaps (rolling):** #15–19 (CAT race, difficulty, dedup, explanations), #34–36 (a11y, upload scope decision, UI affordances).
7. **Polish:** P2/P3 as capacity allows.

---

## Calibration notes

- The **CAT engine being simplified (rule-driven, not 3PL IRT) is explicitly acceptable** per PRD §11.2/§11.3 — that's a deliberate, documented decision, not a gap. The real CAT problem is #16 (uniform difficulty), which silently degrades the matching the MVP *does* require.
- The **JSONL-only import (#35)** is the one place where CLAUDE.md and the PRD appear to disagree on scope — worth confirming intent before building anything.
- The CAT engine's **unit/service/integration test balance is healthy** (`test_cat_engine.py` pure unit + `test_exam_service.py` service-level + `test_exam_api.py` full HTTP loop) — this is the pattern the rest of the suite should aim for.
- Verified **NFRs that are already met**: bcrypt hashing (NFR-SEC-01), login lockout (NFR-SEC-03), all-APIs-auth'd (NFR-SEC-04), RBAC (NFR-SEC-05), parameterized queries (NFR-SEC-06), snapshots (NFR-DATA-01), soft delete (NFR-DATA-02), import rollback (NFR-DATA-04), audit logging (NFR-DATA-05), tenant isolation (NFR-COMP-05).
- Verified **MVP-excluded items correctly absent**: PDF/DOCX parsing, drag/hotspot question types, org billing, AI question generation, offline practice, native mobile app (PRD §12.2).
