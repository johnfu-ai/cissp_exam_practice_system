# P0 #2 — Strong JWT Secret + Dev-Only Admin Reset Design Spec

Date: 2026-07-03
Status: Approved (self-approved under autonomous goal directive)
Parent audit: `docs/audits/2026-07-03-improvement-proposals.md` (P0 #2)
Parent PRD: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` §7.2 (NFR-SEC-02)

## 1. Goal & scope

Two related hardenings from audit P0 #2:

1. **Reject a weak/default JWT secret outside development.** Today
   `jwt_secret` defaults to `change-me` and the dev compose ships
   `JWT_SECRET: dev-only-change-me` with no startup check — anyone who deploys
   without overriding the secret can forge any access token. Add a Settings
   validator that refuses to start in non-dev `app_env` when the secret is the
   default or shorter than 32 chars.
2. **Stop hardcoding `admin/admin` in compose + gate the reset-on-restart
   behind dev mode.** Today `docker-compose.yml` sets `SEED_ADMIN_PASSWORD:
   admin` and `seed.py` resets the admin password to it on *every* restart
   unconditionally — defeating rotation and shipping a known credential. Move
   the dev convenience (admin/admin works in dev) to be driven by `app_env`,
   not a committed secret, and never reset in production.

**Covers:** audit P0 #2 (C-2 + C-3); NFR-SEC-02 (production HTTPS/secret
hygiene — secret-strength portion).

**Out of scope:** full secret management (vault/sops — audit M6); HTTPS
redirect (P0 #6); access-token revocation (P1 #8).

## 2. Behavior changes

### 2.1 Settings validator (`app/core/config.py`)

A `@model_validator(mode="after")` on `Settings`:
- `dev = app_env.lower() in {"development", "dev", "test"}`
- If **not** dev and `jwt_secret in {"change-me", "dev-only-change-me"}` **or**
  `len(jwt_secret) < 32` → raise `ValueError` (prevents app start).
- Dev is allowed to keep the default (tests + local dev rely on it).

### 2.2 Seed admin logic (`app/db/seed.py`)

Introduce `dev_mode = settings.app_env.lower() in {"development", "dev", "test"}`.
Compute `effective_pw`:
- `effective_pw = settings.seed_admin_password or ("admin" if dev_mode else None)`

Admin bootstrap:
- **Admin does not exist:** `pw = effective_pw or secrets.token_urlsafe(16)`;
  create with `hash_password(pw)`. Print the generated password only when
  `effective_pw is None` (prod random) — and print a dev warning when using the
  `admin` default.
- **Admin exists:**
  - If `effective_pw is not None` (dev default `admin`, or any explicit
    `seed_admin_password`): reset to `effective_pw` when the hash differs
    (preserves dev admin/admin-across-restarts + honors operator overrides).
  - If `effective_pw is None` (prod, no explicit password): **do not reset** —
    leave the existing password (the admin sets their own via the UI).

### 2.3 docker-compose.yml

Remove `SEED_ADMIN_PASSWORD: admin` (leave unset). Keep `APP_ENV: dev` so dev
mode still yields admin/admin via the seed default. The dev login button on
the login page (`admin/admin`) continues to work.

## 3. Testing

- `tests/test_config.py` (new):
  - `Settings(app_env="production", jwt_secret="change-me")` raises.
  - `Settings(app_env="production", jwt_secret="dev-only-change-me")` raises.
  - `Settings(app_env="production", jwt_secret="short")` raises (len < 32).
  - `Settings(app_env="production", jwt_secret="x"*32)` OK.
  - `Settings(app_env="development", jwt_secret="change-me")` OK (dev allowed).
  - `Settings(app_env="dev", jwt_secret="change-me")` OK.
- `tests/test_seed.py` (append):
  - dev + no `seed_admin_password` → admin password is `admin`
    (`verify_password("admin", hash)`).
  - prod + no `seed_admin_password` → admin password is random
    (`verify_password("admin", hash)` is False) and a password is printed.
  - prod + existing admin with password X + `seed_admin_password="Y"` → reset
    to Y (operator override honored in prod).
  - prod + existing admin with password X + no `seed_admin_password` → password
    stays X (no reset).
  - dev + existing admin + `seed_admin_password="Z"` → reset to Z.

  (Use `monkeypatch.setattr` on `app.db.seed.settings` or construct with env
  vars via `Settings` overrides + `monkeypatch.setenv`. Prefer
  `monkeypatch.setenv("APP_ENV", ...)` + `monkeypatch.setenv("SEED_ADMIN_PASSWORD", ...)`
  and re-import/refresh settings, OR pass a settings object. Simplest: patch
  `app.db.seed.settings` with a `Settings(...)` instance for the test.)

Existing seed tests run under `app_env="development"` + empty
`seed_admin_password` → admin gets `admin` (dev default); they only assert
`password_hash` truthy, so they stay green.

## 4. Migration

None. No schema changes.

## 5. Acceptance criteria

1. `create_app()` / `Settings()` raises in production with a default/short JWT
   secret; the dev compose still starts.
2. `docker-compose.yml` no longer hardcodes `SEED_ADMIN_PASSWORD`.
3. `admin/admin` still works in the dev container (dev-mode seed default).
4. In prod, the admin password is NOT reset on restart (unless an operator
   explicitly sets `SEED_ADMIN_PASSWORD`).
5. All existing tests pass; new tests pass.
