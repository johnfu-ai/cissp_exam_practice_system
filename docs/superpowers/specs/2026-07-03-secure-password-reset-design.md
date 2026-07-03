# P0 #1 — Secure Password Reset/Change Design Spec

Date: 2026-07-03
Status: Approved (self-approved under autonomous goal directive)
Parent audit: `docs/audits/2026-07-03-improvement-proposals.md` (P0 #1)
Parent PRD: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` §6.1 (FR-USER-03), §7.2 (NFR-SEC-*)

## 1. Goal & scope

Close the unauthenticated account-takeover hole in `POST /api/auth/reset-password`,
which today accepts `{email, new_password}` with **no auth, no old-password
proof, and no email-delivered token** — anyone who knows an email (including the
public seed-admin email) resets that account's password in a single request.

Replace it with three secure flows and remove the vulnerable one:

1. **Authenticated password change** — the in-app "I know my password" path.
2. **Token-based self-service reset** — the "I forgot my password" path,
   forward-compatible with email delivery (no email service exists today).
3. **Admin-assisted reset** — the production fallback for forgotten passwords
   when no email is configured (self-hosted deployment).

**Covers:** audit P0 #1; PRD FR-USER-03 (P1) promoted to a real token flow;
NFR-SEC-02/03/04 (auth required, no enumeration, audit logged).

**Out of scope (later items):** access-token revocation on password change
(audit P1 #8 — requires a `jti` revocation list / token versioning); email/SMS
delivery of the reset token (no mail infra); per-IP rate limiting middleware
(audit P1 #10 — the reset *request* endpoint reuses the existing lockout store
for per-email throttling in the meantime).

## 2. Threat model closed

| Threat (current) | Closure |
|---|---|
| Unauthenticated caller resets any account by email | Old endpoint removed; reset requires a single-use token bound to the user, or admin auth. |
| Email enumeration via 404-vs-200 on reset | `request` endpoint always returns `200 {"ok": true}` regardless of whether the email exists. |
| Timing oracle on reset (user-exists faster) | `request` does the same work (token issue attempt) regardless; no short-circuit on missing user. |
| Reset not audited distinctly | New `AuditAction.password_reset` + `password_change` values; admin reset logs actor = admin. |
| Token replay | Reset tokens are single-use (`consume` = atomic get-and-delete); 15-min TTL. |

## 3. Credential model additions

A **password-reset token**: 32-byte URL-safe random string; Redis key
`pwreset:{token}` → JSON `{"user_id": "..."}` with TTL
`settings.password_reset_token_ttl_minutes` (default 15). Single-use: looking
it up deletes it. Redis is chosen for parity with the refresh-token store and
instant expiry.

`PasswordResetTokenStore` (Protocol) with `InMemoryPasswordResetTokenStore`
(tests) and `RedisPasswordResetTokenStore` (prod), mirroring the refresh-store
pattern in `app/core/security.py`.

## 4. New backend files / changes

```
app/core/config.py        # +password_reset_token_ttl_minutes (15)
app/core/security.py      # +PasswordResetTokenStore + InMemory/Redis impls
app/models/enums.py       # +AuditAction.password_reset, +AuditAction.password_change
app/alembic/versions/<new>.py  # ALTER TYPE audit_action ADD VALUE (x2)
app/schemas/auth.py       # +PasswordChangeIn, ResetPasswordRequestIn, ResetPasswordConfirmIn
                          # -ResetPasswordIn (removed)
app/services/auth.py      # +change_password, request_password_reset, confirm_password_reset
app/dependencies.py       # +get_reset_token_store()
app/api/auth.py           # PUT /password; POST /reset-password/request; POST /reset-password/confirm
                          # -POST /reset-password (removed)
app/schemas/admin.py      # +AdminResetPasswordIn
app/services/admin.py     # +admin_reset_password
app/api/admin.py          # POST /users/{user_id}/reset-password
tests/test_auth_service.py  # +tests for the three service flows
tests/test_auth_api.py      # rewrite reset tests for the new endpoints
tests/test_admin_service.py # +admin_reset_password test
tests/test_admin_api.py     # +admin reset endpoint test
```

No new tables. One Alembic migration (enum value additions only).

## 5. Settings additions

`config.py`:
- `password_reset_token_ttl_minutes: int = 15`

## 6. Flow specifications

### 6.1 Authenticated password change — `PUT /api/auth/password`

- **Auth:** valid access token (`get_current_user`).
- **Body:** `PasswordChangeIn {current_password: str, new_password: str (min 8)}`.
- **Behavior:**
  1. `verify_password(current_password, user.password_hash)` — on failure raise
     `AuthError(401, "incorrect current password")`. Run a dummy verify when the
     user has no password hash (future OAuth-only) to keep timing flat.
  2. `user.password_hash = hash_password(new_password)`.
  3. `log_audit(action=password_change, actor=user, entity="user", entity_id=user.id)`.
  4. Commit. Return `{"ok": true}`.
- **Session invalidation:** existing refresh tokens remain valid until natural
  expiry in this item (full revocation is P1 #8). Documented as a known follow-up.

### 6.2 Reset request — `POST /api/auth/reset-password/request`

- **Auth:** none.
- **Body:** `ResetPasswordRequestIn {email: EmailStr}`.
- **Behavior:**
  1. Per-email throttling via `lockout_store`: if `is_locked(email)` → 429.
     `record_failure(email)` on every call (success or not) up to threshold —
     this bounds request rate per email. On a successful issue, `lockout_store.reset(email)`.
  2. Look up user by lowercased email. **If missing, still return 200** (no leak).
  3. If present: `token = reset_store.issue(user.id)`; the token is **not** sent
     by the API in production. When `settings.app_env == "development"` the
     response includes `"token": <token>` so the flow is testable end-to-end
     without email (a real deployment emails the link — future work).
  4. `log_audit(action=password_reset, actor=None, entity="user",
     entity_id=user.id, details={"phase": "requested"})` only when the user
     exists (so audit doesn't fill with noise for unknown emails).
  5. Return `{"ok": true}` (+ `"token"` in dev).

### 6.3 Reset confirm — `POST /api/auth/reset-password/confirm`

- **Auth:** none.
- **Body:** `ResetPasswordConfirmIn {token: str, new_password: str (min 8)}`.
- **Behavior:**
  1. `user_id = reset_store.consume(token)` — single-use (get + delete). If
     `None` → `AuthError(401, "invalid or expired reset token")`.
  2. Load user; if missing or disabled → 401/403 (delete token already happened).
  3. `user.password_hash = hash_password(new_password)`.
  4. `log_audit(action=password_reset, actor=user, entity="user",
     entity_id=str(user.id), details={"phase": "confirmed"})`.
  5. Commit. Return `{"ok": true}`.

### 6.4 Admin-assisted reset — `POST /api/admin/users/{user_id}/reset-password`

- **Auth:** `require_permission("admin:manage_users")` (org-scoped for
  `org_admin`, global for `system_admin` — reuses `get_user` scope check → 404
  on cross-org).
- **Body:** `AdminResetPasswordIn {new_password: str | None}`. If `new_password`
  is omitted, generate a random one (`secrets.token_urlsafe(12)`) and return it
  (the admin relays it to the user out-of-band).
- **Behavior:**
  1. Resolve + scope-check the target user (reuse `get_user`'s scope logic).
  2. `user.password_hash = hash_password(new_password or generated)`.
  3. `log_audit(action=password_reset, actor=current.user, entity="user",
     entity_id=str(user_id), details={"by": "admin"})`.
  4. Commit. Return `{"ok": true, "password": <generated>}` when generated,
     else `{"ok": true}`.

### 6.5 Removed

`POST /api/auth/reset-password {email, new_password}` is **deleted**. The
`ResetPasswordIn` schema is removed.

## 7. RBAC / tenant scoping

- `PUT /api/auth/password` and the reset endpoints are user-scoped (no
  permission code; identity from the token or the reset token's bound user).
- The admin reset route reuses `require_permission("admin:manage_users")` and
  the existing `_admin_org_scope` / `get_user` cross-org → 404 behavior.

## 8. Migration

One Alembic revision (`down_revision` = the current head `2668af3a57ef`):
- `op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'password_reset'")`
- `op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'password_change'")`
- Downgrade: PG has no `DROP VALUE` for enums prior to PG13; even PG13+ lacks a
  clean `ALTER TYPE ... DROP VALUE`. The downgrade is a documented **no-op** that
  raises `NotImplementedError` if invoked below head (enum value removal is
  unsafe and rarely needed). Documented in the migration.

The no-autogenerate-drift test (`tests/test_migrations.py`) must remain green:
the Python `AuditAction` enum gains the two values to match the DB type.

## 9. Frontend

- **`/settings`**: add a "Change password" card (current password + new
  password + confirm). Calls `PUT /api/auth/password`. Toast on success/error.
- **`/forgot-password`** page (linked from the login page): email → request →
  (in dev, display the returned token) → token + new password → confirm →
  redirect to login. In production the token field is still shown (the email
  link the user clicks will carry `?token=…`, prefilling it).
- **Login page**: add a "Forgot password?" link to `/forgot-password`.
- Locale dictionaries (`en.ts`/`zh.ts`): new keys for both cards; parity test
  must pass.

## 10. Testing

- `tests/test_auth_service.py`:
  - `change_password` rejects wrong current password; updates hash; audits
    `password_change`.
  - `request_password_reset` issues a single-use token; returns `None`-ish for
    unknown email without raising; throttles per email.
  - `confirm_password_reset` succeeds with a valid token; fails after first use
    (single-use); fails with bogus token; audits `password_reset`.
- `tests/test_auth_api.py`:
  - `PUT /api/auth/password` 401 without token, 401 wrong current, 200 success.
  - `POST /reset-password/request` always 200; returns `token` in dev; unknown
    email still 200 and no token-issuing side effect beyond throttle.
  - `POST /reset-password/confirm` 200 with valid token; 401 with consumed/
    bogus token; new password logs in.
  - The old `POST /reset-password` returns 404 (removed).
- `tests/test_admin_service.py` + `test_admin_api.py`:
  - Admin reset sets password (audited `password_reset`); generates a random
    password when omitted; cross-org target → 404; non-admin → 403.
- `tests/test_migrations.py`: drift test still green after the enum migration.

## 11. Acceptance criteria

1. The old `POST /api/auth/reset-password {email,new_password}` is gone (404).
2. An unauthenticated attacker cannot reset any account's password knowing only
   the email — the request endpoint returns no usable credential in production,
   and confirm requires a single-use token.
3. `PUT /api/auth/password` requires the current password; wrong current → 401.
4. Admin reset is permission-gated, org-scoped, and audit-logged as
   `password_reset`.
5. No email enumeration: `request` returns 200 for unknown emails.
6. Reset tokens are single-use and expire after 15 min.
7. All existing tests still pass; new tests pass; migration drift is zero.
8. Frontend change-password + forgot-password flows work end-to-end against the
   backend in dev mode.
