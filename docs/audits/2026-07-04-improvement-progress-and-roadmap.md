# CISSP Exam System — Improvement Progress & Roadmap

**Date:** 2026-07-04
**Supersedes-in-scope:** `docs/audits/2026-07-03-improvement-proposals.md` (the 36-proposal audit). That audit remains the canonical `file:line` reference; this doc tracks what got done after it and what remains.

All P0 items (#1–#6) are DONE and merged to `master`. This doc covers the P1/P2/P3 backlog.

---

## Completed since the 2026-07-03 audit

Verified against commit history on `master` (HEAD `aae28be` at time of writing).

| # | Proposal | Status | Done by |
|---|----------|--------|---------|
| 6 | `/health` readiness + TLS + safe migrations | ✅ DONE | P0 #6 (`194afd3`, `80a38fe`) |
| 12 | Btree indexes on high-traffic FK columns | ✅ DONE | `aa2a910` (migration `6dad1bddd1d2`) |
| 14 | Paginate unbounded list endpoints | ✅ DONE | `4db385d` |
| 15 | Serialize CAT/practice answer submits (row-lock + unique constraint) | ✅ DONE | `0b22e44` (migration `2f0684f4fbb6`) |
| 17 | Three-level dedup — stem-hash skip + conflict surfacing | ✅ DONE | `c1d10a3` (migration `6ffc62628b99`) |
| 19 | Partial-zh 1:1 option pairing (§10.2 r8) + empty-stem/explanation publish blocking (rule 6) | ✅ DONE | `3aa0e18` (partial-zh) + FR-LANG-09 `_translation_publishable` gate on `approve` (language-selection merge) |
| 20 | CI pipeline (GitHub Actions: backend pytest + frontend vitest/lint/build) | ✅ DONE | `aae28be` — first run green on `master` |
| 29 | Frontend error boundaries + 401 redirect | ✅ DONE | `6558ec7` (`error.tsx`, `global-error.tsx`) |
| 9 | Concurrent-401 refresh race → singleton refresh promise; refresh token → httpOnly cookie | ✅ DONE (`fix/p1-httponly-cookie`) - singleton refresh (`6558ec7`) + refresh token moved to an httpOnly `SameSite=lax` `Path=/api/auth` cookie (set on login/register/refresh, cleared on logout; `/refresh`+`/logout` cookie-first/body-fallback; `TokenOut.refresh_token` now None in body so XSS can't read it from the login response). Frontend stores only the 60-min access token; `api.refreshOnce()` posts with credentials:include + empty body. 556 backend + 112 frontend tests, zero drift, e2e-verified (real-backend curl: login sets HttpOnly cookie, cookie-based /refresh -> 200, no cookie -> 401). |
| 16 | CAT difficulty variation | ◐ PARTIAL | `172df28` — `update_ability` now weights by difficulty; **ETL still hardcodes `DIFFICULTY_DEFAULT`** (`transform.py:116`), so ability-matching is still meaningless in practice |
| 36 | Forgot-password page | ◐ PARTIAL | P0 #1 (`0162a9d`) — forgot-password done; practice timer / option shuffling / same-KP recommendation / notes CRUD still open |
| 11 | Drop unmaintained `passlib`; call `bcrypt` directly | ✅ DONE (2026-07-04) | `fb7f69b` — direct bcrypt in `security.py`; `$2b$` backward-compat; passlib removed from requirements; warning gone |
| 8 | Revocable access tokens + reject disabled users | ✅ DONE (2026-07-04) | `3a9f4d9` — `RevokedTokenStore` (logout kills access jti); `get_current_user` checks revoked + disabled-status + loads perms fresh from DB (no 60-min staleness) |
| 7 | Refresh-token reuse detection + family invalidation | ✅ DONE (2026-07-04) | `1f00010` — `family_id` on refresh tokens; `rotate` marks old `rotated` (kept for detection); reuse → `revoke_family` + 401 + audit |
| 10 | Per-IP rate limiting + login timing oracle | ✅ DONE (2026-07-04) | `6190433` — `RateLimiter` on /login, /register, /reset-password (configurable `login_rate_limit`/`window`); `authenticate` does a dummy bcrypt on missing user (constant-time) |

**Net:** 12 P1 items fully closed (#6, #8, #7, #10, #11, #12, #14, #15, #17, #19, #20, #29), 3 partially closed (#9, #16, #36). **Tier 1 (open security holes) is complete.** The audit's "recommended order" steps 1, 2, 4 (auth hardening), and the perf/correctness core of steps 5–6 are done.

---

## Still open — prioritized

### 🔴 Tier 1 — open security holes — ✅ COMPLETE (2026-07-04)

All four Tier 1 security items are done on branch `fix/p1-tier1-security` (#11 `fb7f69b`, #8 `3a9f4d9`, #7 `1f00010`, #10 `6190433`). 521 backend + 97 frontend tests pass. See the commit messages for design details. Remaining auth follow-up (not Tier 1): #9 httpOnly-cookie storage, #11 password-policy strengthening (breach-list/complexity), and a per-user `tokens_invalid_before` so password change invalidates access tokens issued in *other* sessions.

### 🟠 Tier 2 — production readiness (blocks any non-local deployment)

| # | Proposal | Why it matters | Effort |
|---|----------|----------------|--------|
| 25 | Backups + Redis durability | Postgres: named volume, no `pg_dump`/cron/restore tested (PRD §7.3 requires daily backup). Redis: no volume/persistence → restart logs out every user and clears all lockouts. | 1–2 days |
| 24 | Multiple uvicorn workers + graceful shutdown | Single sync worker + bcrypt-on-event-loop = no prod concurrency. No SIGTERM/lifespan → in-flight exam submissions killed on deploy. | 1 day |
| 26 | Observability | No structured logging, no request IDs, no metrics, no Sentry. Default uvicorn access logs only. | 1–2 days |
| 27 | Harden Dockerfiles | Both run as root; neither multi-stage (gcc/libpq-dev + node_modules ship in final image); minimal `.dockerignore`; `npmmirror.com` hardcoded in frontend build. | 0.5–1 day |
| 28 | Resource limits + restart policies + prod/dev compose split | No mem/cpu limits, no `restart:`, one compose for dev and "prod." | 0.5 day |

### 🟡 Tier 3 — performance & PRD correctness

| # | Proposal | Why it matters | Effort |
|---|----------|----------------|--------|
| 13 | N+1 queries in hot paths | Biggest perf risk: question list 101 queries/page; exam review 300+ queries for a 150-item exam; analytics `personal_report` scans the **entire** `question_mappings` table per request. | 2–3 days |
| 16 (data) | Read/derive `difficulty` from source in ETL | ✅ DONE (`feat/p3-etl-difficulty-option-explanations`) - `RawQuestion.difficulty` parsed from source (int/label, clamped 1-5); `transform._resolve_difficulty` uses source difficulty when present, else a coarse type-based prior (multiple_choice→4, true_false→2, else 3) so the CAT pool is no longer uniform; `_differs` now compares difficulty so enrichment lands on re-import. | 1 day |
| 18 | Per-option explanations + read `difficulty`/`license` from source | ✅ DONE (`feat/p3-etl-difficulty-option-explanations`) - `option_explanations`/`option_explanations_zh` (split or nested) parsed + carried to `QuestionTranslation.options[].explanation`; `license_status` read from source (default unconfirmed, FR-ETL-09); `_differs` detects both. 552 backend tests, zero drift. | 1 day |
| 34 | Keyboard answer selection/submission + WCAG contrast | **PRD P0** (NFR-UX-04): no `onKeyDown` in any runner. `--success` (#34C759) / `--destructive` (#FF3B30) on white fail AA 4.5:1. | 1–2 days |
| 22 | Real downgrade + drift-meta tests | Only downgrade test runs on an empty DB (asserts nothing). The `a1b2c3d4e5f6` bilingual-merge downgrade is lossy and untested. Add a test-of-the-test that the drift guard catches a real model change. | 1 day |
| 23 | Concurrency + N+1 query-count tests; coverage | No tests assert the CAT race is safe, none bound query counts (an N+1 regression passes green), no `pytest-cov`. | 1–2 days |
| 21 | Make conftest not require CREATEDB | CI works (superuser), but the container/non-superuser test-runner still can't run tests. Lower priority now that CI exists. | 0.5 day |

### Frontend (P1, not security)

| # | Proposal | Why it matters |
|---|----------|----------------|
| 30 | Handle errors in auth forms | ✅ DONE (`fix/p1-frontend-polish`) - login `try/catch` (network errors -> friendly `auth.networkError`, no more unhandled rejection); register gains busy state + `try/catch` + friendly non-409 error (`auth.registerFailed`) instead of the raw backend JSON body. New locale keys `auth.networkError`/`auth.registerFailed` (en+zh). |
| 31 | Invalidate React Query caches on mutations | ✅ DONE (`fix/p1-frontend-polish`) - `useCreateQuestion`/`useUpdateQuestion`/`useDeleteQuestion`/`useReviewQuestion` invalidate the `questions.list` cache (delete also removes the detail); `useUpdateQuestionState` invalidates `analytics` + `practice.session` roots. New `questions.test.tsx` asserts invalidation. |
| 32 | Generate API types from OpenAPI | 710 lines of hand-written types will silently drift. Use `openapi-typescript` against `/openapi.json` + a CI drift check. |
| 33 | Fix i18n bypass + parity test | ✅ DONE (`fix/p1-frontend-polish`) - the two `labelize` Title-Case helpers removed from `runner.tsx` + `create-session-form.tsx`; all enum labels now route through `enumLabel(t, scope, ...)` (qType/errorType + new `subset`/`orderMode` scopes, en+zh). i18n parity test strengthened: bidirectional key parity + non-empty zh leaves + zh is not a wholesale copy of en. |
| 36 (rem) | Practice timer display / option shuffling / same-KP recommendation / notes CRUD | FR-ANS-07/08, FR-PRAC-09. Backend tracks `elapsed_ms` but runner never shows it. |

### PRD scope decision (confirm intent)

| # | Proposal | Note |
|---|----------|------|
| 35 | CSV/XLSX/JSON file upload (FR-IMP-01) | CLAUDE.md frames JSONL-only as intentional; PRD §12.1/§14.1 list CSV/XLSX/JSON as MVP must-include. **Product decision, not a bug** — confirm with PRD owner before building. |

### P2/P3 — as capacity allows

See the original audit's P2/P3 sections. Highlights: centralize transaction management in `get_session`; unify the duplicated service exception hierarchy; split `ExamSession.config` JSONB (client-visible vs internal); cache the CAT candidate pool; move analytics aggregation to SQL; frontend polish (`<Link>`/`router.replace`/`AlertDialog`); restrict CORS; tune DB pool; add `typecheck` + stricter `tsconfig`.

---

## Session follow-ups (small, from the 2026-07-04 dedup/CI work)

- **Frontend `/import` wizard**: `preview_summary` now carries `duplicates` + `conflicts`, but the UI doesn't display them — content editors can't see which records were skipped as duplicates. Small UX gap.
- **`CLAUDE.md` "Current State"**: no FR-ETL-08 dedup entry (should follow the P0 #1–#6 format).
- **`BilingualText` duplicate-render edge case** (carried from v1.1): when one language is null in bilingual mode.

---

## Recommended next picks

By impact ÷ effort:

1. **#11 (passlib)** — half a day, the suite is actively warning, pure mechanical swap. Quick win to clear the noise before anything else.
2. **#8 (token revocation)** — 1–2 days, the largest open security hole; pairs naturally with **#7** (refresh reuse) since both touch the token store.
3. Then branch on intent:
   - **Going to real deployment?** → Tier 2: #25 (backups) + #24 (workers/graceful shutdown) + #26 (observability).
   - **Scaling to load?** → #13 (N+1) + #16-data (CAT difficulty).
   - **PRD completeness?** → #34 (a11y, P0) + #36-rem (practice affordances).

A coherent 1-week security batch: **#11 → #8 → #7 → #10**. That closes every open auth/session hole from the audit.
