# Sub-project B — Auth & RBAC Design Spec

Date: 2026-06-22
Status: Approved (self-approved under autonomous goal directive)
Parent PRD: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` §6.1, §7.2, §9.5

## 1. Goal & scope

Make the system authenticate users and enforce permission-based access on all
non-public APIs, repaying the ETL "unauthenticated stubs" debt. Backend service
+ endpoints + minimal frontend (login/register/logout), testable end-to-end.

**Covers:** FR-USER-01, FR-USER-02, FR-USER-04 (P0); FR-USER-03 (P1, email-free
password reset stub); NFR-SEC-01, NFR-SEC-03, NFR-SEC-04, NFR-SEC-05.

**Out of scope (later sub-projects):** profile/avatar/exam-target-date
(FR-USER-06, P2); org-space isolation UX (FR-USER-05, P1 — data model exists);
full user-management admin UI.

## 2. Credential model

JWT access token (HS256, `settings.access_token_expire_minutes` = 60) + opaque
refresh token (~14 d) stored in Redis for revocation.

- **Access token** claims: `sub` (user_id), `org_id` (active org), `roles`
  (list of role-name strings), `perms` (sorted list of permission codes), `exp`,
  `iat`, `jti`. Signed with `settings.jwt_secret`.
- **Refresh token**: 32-byte URL-safe random string; Redis key `refresh:{token}`
  → JSON `{user_id, org_id, expires_at}`. Rotated on use (old key deleted, new
  token returned). Logout = delete the Redis key.
- Redis is chosen for instant revocation and to support login lockout
  (NFR-SEC-03); it is already a project dependency.

## 3. New backend files

```
app/core/security.py     # password hashing (bcrypt), JWT encode/decode, refresh token gen/verify/store
app/services/auth.py     # register_user, authenticate, issue_tokens, refresh_tokens, logout
app/dependencies.py      # get_current_user, get_active_org_id, require_permission(code) factory
app/api/auth.py          # /api/auth/{register,login,refresh,me,logout} router
app/schemas/auth.py      # Pydantic request/response models
```

`app/dependencies.py` is the cross-cutting home; later sub-projects import
`require_permission` from here.

## 4. Settings additions

`config.py`:
- `refresh_token_expire_days: int = 14`
- `bcrypt_rounds: int = 12`
- `login_lockout_threshold: int = 5`
- `login_lockout_window_minutes: int = 15`

Keep existing `jwt_secret`, `jwt_algorithm`, `access_token_expire_minutes`.
Warn (not fail) when `jwt_secret == "change-me"` outside tests.

## 5. Password hashing

bcrypt via `passlib[bcrypt]` (NFR-SEC-01). `User.password_hash` is already
nullable to support future OAuth-only users.

## 6. Registration & login flow

- **Register** `POST /api/auth/register {email, password, display_name?}`:
  - Case-fold email; reject duplicates (409, relies on `uq_users_email_lower`).
  - Create `User` (password_hash), a **personal `Organization`**
    (`kind=personal`, slug `personal-{uuid8}`), an `OrganizationMembership`
    (user, personal_org, role=individual_learner), set `default_organization_id`.
  - Issue tokens for the new user/org; return user + tokens.
- **Login** `POST /api/auth/login {email, password}`:
  - Verify hash. On success: issue tokens, write `AuditLog(login)`.
  - On failure: increment Redis `loginfail:{email_lower}` (TTL = window). At
    ≥ threshold within window → 429 with retry-after; do not leak which of
    "no such user" vs "wrong password".
- **Refresh** `POST /api/auth/refresh {refresh_token}`: verify Redis key,
  rotate, return new pair. Unknown/expired token → 401.
- **Me** `GET /api/auth/me`: user + active org + perms list.
- **Logout** `POST /api/auth/logout`: delete refresh Redis key, write
  `AuditLog(logout)`.
- **Password reset** `POST /api/auth/reset-password {email, new_password}`:
  MVP email-free stub (FR-USER-03 minimal). Resets password directly when the
  caller proves email ownership out-of-band — acceptable for self-hosted
  single-user MVP; flagged TODO for email-token flow. Rate-limited like login.

## 7. RBAC dependency

`require_permission(code: str)` returns a FastAPI dependency:
1. Read `Authorization: Bearer <access>`; decode/verify JWT. 401 if missing/
   invalid/expired.
2. Resolve `current_user` (DB row) and `active_org_id` (from claim).
3. Collect permission codes for the user's membership in the active org.
4. 403 if `code` not in the set.

`get_current_user` and `get_active_org_id` are exposed as standalone
dependencies for routes that need identity but not a specific permission.

**Active org:** the token carries `org_id` (the membership used at login). For
MVP the personal org is the default; org-switching is a later sub-project.

## 8. ETL routes — repay the debt

Replace the `_org_id()` stub with `active_org_id` from the dependency; pass
`initiated_by_id=current_user.id` where the runner accepts it.

| Route | Permission |
|---|---|
| `GET /datasets`, `GET /datasets/{slug}` | `question:import` |
| `GET /runs`, `GET /runs/{id}` | `question:import` |
| `POST /runs`, `POST /runs/{id}/commit`, `POST /runs/{id}/rollback` | `question:import` |
| `GET /mappings` | `admin:manage_taxonomy` |
| `POST/PUT/DELETE /mappings` | `admin:manage_taxonomy` |

Update existing `tests/etl/test_api_etl.py` to authenticate as the seed admin;
assert 401 without a token and 403 with an insufficient role.

## 9. Seed additions

Add **one bootstrap system_admin** so the system is usable on first run:
- `seed_admin_email` (default `admin@example.com`) and `seed_admin_password`
  (env; if unset, generate a random password and print it once).
- Membership on the personal org with `system_admin` role.
- Bump `SEED_VERSION` to `"3"`.

Without this, no one can hit the ETL admin routes after lock-down.

## 10. Frontend (minimal)

Client-side token store (Zustand) holding access+refresh tokens in memory,
mirrored to `sessionStorage` for reload survival. An API client
(`lib/api.ts`) attaches the bearer header and auto-refreshes once on 401.

Pages/components:
- `frontend/src/app/(auth)/login/page.tsx` — email/password form.
- `frontend/src/app/(auth)/register/page.tsx` — email/password/display_name.
- `frontend/src/components/auth-guard.tsx` — wraps protected pages, redirects
  to /login when unauthenticated.
- `frontend/src/lib/auth-store.ts`, `frontend/src/lib/api.ts`.
- Existing home page: show login/logout + user email; link to ETL dataset list
  as a smoke test of authenticated API access.

CORS: backend allows the frontend origin with credentials.

## 11. Testing

- `tests/test_security.py`: hash/verify, JWT encode/decode/expire, refresh
  store/verify/rotate/revoke.
- `tests/test_auth_api.py`: register (success, dup email, validation), login
  (success, wrong password, lockout), refresh (success, rotation, revoked),
  me, logout, reset-password. Audit rows written for login/logout.
- `tests/test_dependencies.py`: `require_permission` allow/deny, 401 vs 403,
  tenant `active_org_id` propagation.
- Update `tests/etl/test_api_etl.py`: authenticated calls; 401/403 cases.

## 12. Migration

No schema changes — all auth models already exist. Only a `SEED_VERSION` bump.
No Alembic revision required.

## 13. Acceptance criteria

1. A user can register, log in, refresh, and log out via the API.
2. Wrong password 5× within 15 min locks the account for 15 min (429).
3. Every ETL route returns 401 without a token and 403 with an insufficient
   role; 200 with the seed admin token.
4. Login/logout produce `AuditLog` rows.
5. The frontend login/register pages work end-to-end against the backend, and
   the home page reflects the authenticated state.
6. All existing tests still pass; new tests pass.
