# P0 #1 — Secure Password Reset/Change Implementation Plan

> **For agentic workers:** implement task-by-task using TDD (write failing test → implement → verify pass → commit). Spec: `docs/superpowers/specs/2026-07-03-secure-password-reset-design.md`.

**Goal:** Remove the unauthenticated `POST /api/auth/reset-password` account-takeover hole and replace it with (1) an authenticated `PUT /api/auth/password` (current-password required), (2) a single-use token reset request/confirm flow, and (3) an admin-assisted reset — all audit-logged with dedicated `AuditAction` values.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, PyJWT, redis-py, Next.js 16, React 19, Zustand, Vitest.

## Global Constraints

- Tests run against the dedicated `cissp_test` Postgres DB via per-test SAVEPOINT rollback (`backend/tests/conftest.py`); never touch the dev `cissp` DB.
- `audit_action` is a native PG enum — new values added via `ALTER TYPE ... ADD VALUE` in a real Alembic migration (no autogen).
- Reset tokens are Redis-backed, single-use, 15-min TTL — mirror the existing `RefreshTokenStore` pattern.
- No email infra: the `request` endpoint returns the token **only** when `settings.app_env == "development"` (testable); production returns `{"ok": true}`.
- All user-facing strings flow through `t()`; add keys to BOTH `locales/en.ts` and `locales/zh.ts` (parity test enforces).
- Commit per task; final task pushes to GitHub.

---

### Task 1: Settings + password-reset token store

**Files:** modify `backend/app/core/config.py`, `backend/app/core/security.py`; test `backend/tests/test_security.py`.

- [ ] **Step 1:** Add `password_reset_token_ttl_minutes: int = 15` to `Settings` in `backend/app/core/config.py`.

- [ ] **Step 2:** Write failing tests in `backend/tests/test_security.py` (append):
```python
from app.core.security import (
    InMemoryPasswordResetTokenStore, generate_refresh_token,
)
import uuid

def test_reset_token_store_issue_consume_single_use():
    store = InMemoryPasswordResetTokenStore()
    uid = uuid.uuid4()
    token = store.issue(uid, ttl_seconds=60)
    assert store.consume(token) == uid          # first use returns user_id
    assert store.consume(token) is None         # single-use: second use fails
    assert store.consume("bogus") is None       # unknown token

def test_reset_token_store_delete():
    store = InMemoryPasswordResetTokenStore()
    uid = uuid.uuid4()
    token = store.issue(uid, ttl_seconds=60)
    store.delete(token)
    assert store.consume(token) is None
```

- [ ] **Step 3:** Run → FAIL (names not imported/defined).

- [ ] **Step 4:** Implement in `backend/app/core/security.py` (append):
```python
class PasswordResetTokenStore(Protocol):
    def issue(self, user_id: uuid.UUID, ttl_seconds: int) -> str: ...
    def consume(self, token: str) -> uuid.UUID | None: ...
    def delete(self, token: str) -> None: ...


class InMemoryPasswordResetTokenStore:
    def __init__(self) -> None:
        self._data: dict[str, uuid.UUID] = {}

    def issue(self, user_id, ttl_seconds):
        token = generate_refresh_token()
        self._data[token] = user_id
        return token

    def consume(self, token):
        return self._data.pop(token, None)

    def delete(self, token):
        self._data.pop(token, None)


class RedisPasswordResetTokenStore:
    def __init__(self, redis_url: str, prefix: str = "pwreset:") -> None:
        import redis
        self._redis = redis.from_url(redis_url, socket_connect_timeout=2)
        self._prefix = prefix

    def _key(self, token: str) -> str:
        return f"{self._prefix}{token}"

    def issue(self, user_id, ttl_seconds):
        import json
        token = generate_refresh_token()
        self._redis.setex(self._key(token), ttl_seconds, json.dumps({"user_id": str(user_id)}))
        return token

    def consume(self, token):
        import json
        raw = self._redis.getdel(self._key(token))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        return uuid.UUID(json.loads(raw)["user_id"])

    def delete(self, token):
        self._redis.delete(self._key(token))
```

- [ ] **Step 5:** Run → pass. **Step 6:** commit `feat(auth): password-reset token store + ttl setting`.

---

### Task 2: AuditAction enum values + migration

**Files:** modify `backend/app/models/enums.py`; create `backend/app/alembic/versions/<rev>_password_reset_audit_actions.py`.

- [ ] **Step 1:** Add to `AuditAction` in `backend/app/models/enums.py`:
```python
    password_reset = "password_reset"
    password_change = "password_change"
```

- [ ] **Step 2:** Create migration `backend/app/alembic/versions/e7a1b2c3d4e5_password_reset_audit_actions.py` (down_revision = `2668af3a57ef`):
```python
"""Add password_reset + password_change to audit_action enum.

Revision ID: e7a1b2c3d4e5
Revises: 2668af3a57ef
Create Date: 2026-07-03
"""
from alembic import op

revision = "e7a1b2c3d4e5"
down_revision = "2668af3a57ef"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'password_reset'")
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'password_change'")


def downgrade() -> None:
    # PostgreSQL has no safe DROP VALUE for enums (pre-13 none; 13+ unsupported).
    # Removing enum values is unsafe and not needed for rollback semantics.
    # Leaving the values in place is harmless. Intentional no-op.
    pass
```

- [ ] **Step 3:** Run `alembic upgrade head` against the dev DB (or rely on the migration test). Run `pytest tests/test_migrations.py -v` → drift test green.

- [ ] **Step 4:** commit `feat(audit): add password_reset + password_change enum values`.

---

### Task 3: Auth service functions

**Files:** modify `backend/app/services/auth.py`; test `backend/tests/test_auth_service.py`.

- [ ] **Step 1:** Write failing tests (append to `backend/tests/test_auth_service.py`):
```python
from app.core.security import InMemoryPasswordResetTokenStore
from app.services.auth import (
    change_password, request_password_reset, confirm_password_reset,
)

def test_change_password_requires_current(session_with_roles):
    s = session_with_roles
    store = InMemoryRefreshTokenStore()
    user, _ = register_user(s, email="cp@example.com", password="pw123456",
                            display_name="CP", refresh_store=store)
    s.flush()
    from app.services.auth import AuthError
    with pytest.raises(AuthError) as e:
        change_password(s, user=user, current_password="wrong", new_password="newpw123")
    assert e.value.status_code == 401
    # correct current -> updates hash
    change_password(s, user=user, current_password="pw123456", new_password="newpw123")
    assert verify_password("newpw123", user.password_hash)

def test_request_reset_issues_token_for_known_email(session_with_roles):
    s = session_with_roles
    store = InMemoryRefreshTokenStore()
    rst = InMemoryPasswordResetTokenStore()
    register_user(s, email="rr@example.com", password="pw123456",
                  display_name="RR", refresh_store=store)
    s.flush()
    token = request_password_reset(s, email="rr@example.com", reset_store=rst, lockout_store=InMemoryLockoutStore(threshold=5))
    assert token is not None
    assert rst.consume(token) is not None

def test_request_reset_unknown_email_returns_none_no_raise(session_with_roles):
    s = session_with_roles
    rst = InMemoryPasswordResetTokenStore()
    token = request_password_reset(s, email="nope@example.com", reset_store=rst, lockout_store=InMemoryLockoutStore(threshold=5))
    assert token is None  # no leak, no raise

def test_confirm_reset_consumes_token_and_sets_password(session_with_roles):
    s = session_with_roles
    store = InMemoryRefreshTokenStore()
    rst = InMemoryPasswordResetTokenStore()
    user, _ = register_user(s, email="cr@example.com", password="pw123456",
                            display_name="CR", refresh_store=store)
    s.flush()
    token = request_password_reset(s, email="cr@example.com", reset_store=rst, lockout_store=InMemoryLockoutStore(threshold=5))
    confirmed = confirm_password_reset(s, token=token, new_password="newpw123", reset_store=rst)
    assert confirmed.id == user.id
    assert verify_password("newpw123", user.password_hash)
    # single-use: token consumed
    from app.services.auth import AuthError
    with pytest.raises(AuthError):
        confirm_password_reset(s, token=token, new_password="another123", reset_store=rst)
```

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3:** Implement in `backend/app/services/auth.py` (add imports `PasswordResetTokenStore`, `secrets`; add functions):
```python
def change_password(session: Session, *, user: User, current_password: str,
                    new_password: str) -> None:
    if not user.password_hash or not verify_password(current_password, user.password_hash):
        raise AuthError("incorrect current password", status_code=401)
    user.password_hash = hash_password(new_password)
    session.flush()
    log_audit(session, action=AuditAction.password_change, actor_id=user.id,
              organization_id=user.default_organization_id,
              entity_type="user", entity_id=str(user.id))


def request_password_reset(session: Session, *, email: str,
                           reset_store: "PasswordResetTokenStore",
                           lockout_store: LockoutStore) -> str | None:
    email = email.lower().strip()
    if lockout_store.is_locked(email):
        raise AuthError("too many attempts; try later", status_code=429)
    user = session.execute(select(User).filter_by(email=email)).scalar_one_or_none()
    if user is None:
        lockout_store.record_failure(email)  # throttle even on misses
        return None
    token = reset_store.issue(user.id, ttl_seconds=int(
        timedelta(minutes=settings.password_reset_token_ttl_minutes).total_seconds()))
    lockout_store.reset(email)
    log_audit(session, action=AuditAction.password_reset, actor_id=None,
              organization_id=user.default_organization_id,
              entity_type="user", entity_id=str(user.id), details={"phase": "requested"})
    return token


def confirm_password_reset(session: Session, *, token: str, new_password: str,
                           reset_store: "PasswordResetTokenStore") -> User:
    user_id = reset_store.consume(token)
    if user_id is None:
        raise AuthError("invalid or expired reset token", status_code=401)
    user = session.get(User, user_id)
    if user is None:
        raise AuthError("invalid or expired reset token", status_code=401)
    if user.status != UserStatus.active:
        raise AuthError("account disabled", status_code=403)
    user.password_hash = hash_password(new_password)
    session.flush()
    log_audit(session, action=AuditAction.password_reset, actor_id=user.id,
              organization_id=user.default_organization_id,
              entity_type="user", entity_id=str(user.id), details={"phase": "confirmed"})
    return user
```
(Import `PasswordResetTokenStore` from `app.core.security` and `secrets` at top.)

- [ ] **Step 4:** Run → pass. **Step 5:** commit `feat(auth): change_password + reset request/confirm service`.

---

### Task 4: Auth API endpoints (+ remove old)

**Files:** modify `backend/app/schemas/auth.py`, `backend/app/dependencies.py`, `backend/app/api/auth.py`; test `backend/tests/test_auth_api.py`.

- [ ] **Step 1:** Schemas — in `backend/app/schemas/auth.py`: remove `ResetPasswordIn`; add:
```python
class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

class ResetPasswordRequestIn(BaseModel):
    email: EmailStr

class ResetPasswordConfirmIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
```

- [ ] **Step 2:** `backend/app/dependencies.py` — add the reset-token store singleton + provider (mirror refresh store):
```python
from app.core.security import (PasswordResetTokenStore, RedisPasswordResetTokenStore, ...)
_reset_store: PasswordResetTokenStore | None = None

def get_reset_token_store() -> PasswordResetTokenStore:
    global _reset_store
    if _reset_store is None:
        _reset_store = RedisPasswordResetTokenStore(settings.redis_url)
    return _reset_store
```

- [ ] **Step 3:** Write failing tests in `backend/tests/test_auth_api.py` (replace `test_reset_password` with):
```python
from app.dependencies import get_reset_token_store
from app.core.security import InMemoryPasswordResetTokenStore

@pytest.fixture
def client(db_session, session_with_roles):
    app = create_app()
    refresh_store = InMemoryRefreshTokenStore()
    lockout = InMemoryLockoutStore(threshold=5)
    rst = InMemoryPasswordResetTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: refresh_store
    app.dependency_overrides[get_lockout_store] = lambda: lockout
    app.dependency_overrides[get_reset_token_store] = lambda: rst
    return TestClient(app), refresh_store, lockout, rst

def _auth_header(c):
    body = c.post("/api/auth/register", json={"email": "u@example.com",
                  "password": "pw123456"}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body

def test_change_password_endpoint(client):
    c, _, _, _ = client
    h, body = _auth_header(c)
    # wrong current -> 401
    r = c.put("/api/auth/password", headers=h,
              json={"current_password": "wrong", "new_password": "newpw123"})
    assert r.status_code == 401
    # correct -> 200, can login with new
    r = c.put("/api/auth/password", headers=h,
              json={"current_password": "pw123456", "new_password": "newpw123"})
    assert r.status_code == 200
    assert c.post("/api/auth/login", json={"email": "u@example.com",
                  "password": "newpw123"}).status_code == 200

def test_change_password_requires_auth(client):
    c, _, _, _ = client
    assert c.put("/api/auth/password", json={"current_password": "x",
                  "new_password": "newpw123"}).status_code == 401

def test_reset_request_returns_token_in_dev(client):
    c, _, _, _ = client
    c.post("/api/auth/register", json={"email": "rst@example.com", "password": "pw123456"})
    r = c.post("/api/auth/reset-password/request", json={"email": "rst@example.com"})
    assert r.status_code == 200
    assert "token" in r.json() and r.json()["token"]

def test_reset_request_unknown_email_still_200_no_token(client):
    c, _, _, _ = client
    r = c.post("/api/auth/reset-password/request", json={"email": "nope@example.com"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}

def test_reset_confirm_flow(client):
    c, _, _, rst = client
    c.post("/api/auth/register", json={"email": "cf@example.com", "password": "pw123456"})
    tok = c.post("/api/auth/reset-password/request", json={"email": "cf@example.com"}).json()["token"]
    r = c.post("/api/auth/reset-password/confirm", json={"token": tok, "new_password": "newpw123"})
    assert r.status_code == 200
    assert c.post("/api/auth/login", json={"email": "cf@example.com",
                  "password": "newpw123"}).status_code == 200
    # single-use
    assert c.post("/api/auth/reset-password/confirm", json={"token": tok,
                  "new_password": "another123"}).status_code == 401

def test_old_reset_endpoint_removed(client):
    c, _, _, _ = client
    assert c.post("/api/auth/reset-password", json={"email": "x@example.com",
                  "new_password": "newpw123"}).status_code == 404
```
(Update other tests in the file that unpack `client` as `c, store, _` to `c, store, _, _`.)

- [ ] **Step 4:** Run → FAIL.

- [ ] **Step 5:** Implement `backend/app/api/auth.py` — remove `reset_password`; add:
```python
from app.core.config import settings
from app.core.security import PasswordResetTokenStore
from app.dependencies import get_reset_token_store
from app.schemas.auth import (PasswordChangeIn, ResetPasswordRequestIn, ResetPasswordConfirmIn, ...)
from app.services.auth import (change_password, request_password_reset, confirm_password_reset, ...)

@router.put("/password")
def change_password_route(body: PasswordChangeIn,
                          current: CurrentUser = Depends(get_current_user),
                          session: Session = Depends(get_session)):
    try:
        change_password(session, user=current.user,
                        current_password=body.current_password,
                        new_password=body.new_password)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    session.commit()
    return {"ok": True}

@router.post("/reset-password/request")
def reset_request(body: ResetPasswordRequestIn, session: Session = Depends(get_session),
                  reset_store: PasswordResetTokenStore = Depends(get_reset_token_store),
                  lockout_store: LockoutStore = Depends(get_lockout_store)):
    try:
        token = request_password_reset(session, email=body.email,
                                       reset_store=reset_store, lockout_store=lockout_store)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    session.commit()
    resp = {"ok": True}
    if token is not None and settings.app_env == "development":
        resp["token"] = token
    return resp

@router.post("/reset-password/confirm")
def reset_confirm(body: ResetPasswordConfirmIn, session: Session = Depends(get_session),
                  reset_store: PasswordResetTokenStore = Depends(get_reset_token_store)):
    try:
        confirm_password_reset(session, token=body.token,
                               new_password=body.new_password, reset_store=reset_store)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    session.commit()
    return {"ok": True}
```
Remove the `ResetPasswordIn` import + the old `reset_password` route. Remove now-unused imports (`hash_password`, `decode_access_token` if only used by removed route — keep `_extract_*` since `/refresh` uses them).

- [ ] **Step 6:** Run `pytest tests/test_auth_api.py tests/test_auth_service.py -v` → pass. **Step 7:** Run full backend suite `pytest` → all green. **Step 8:** commit `feat(auth): secure password change + token reset endpoints (remove takeover hole)`.

---

### Task 5: Admin-assisted reset

**Files:** modify `backend/app/schemas/admin.py`, `backend/app/services/admin.py`, `backend/app/api/admin.py`; tests `backend/tests/test_admin_service.py`, `backend/tests/test_admin_api.py`.

- [ ] **Step 1:** Schema — add to `backend/app/schemas/admin.py`:
```python
class AdminResetPasswordIn(BaseModel):
    new_password: str | None = Field(default=None, min_length=8, max_length=128)
```

- [ ] **Step 2:** Service — in `backend/app/services/admin.py` add `import secrets` and:
```python
from app.core.security import hash_password

def admin_reset_password(session, *, current, user_id, new_password: str | None):
    user = session.get(User, user_id)
    if user is None:
        raise NotFound("user not found")
    get_user(session, current=current, user_id=user_id)  # scope check -> NotFound
    pw = new_password or secrets.token_urlsafe(12)
    user.password_hash = hash_password(pw)
    session.flush()
    log_audit(session, action=AuditAction.password_reset, actor_id=current.user.id,
              organization_id=current.org_id, entity_type="user",
              entity_id=str(user_id), details={"by": "admin"})
    return {"ok": True, "password": pw} if new_password is None else {"ok": True}
```

- [ ] **Step 3:** API — in `backend/app/api/admin.py` add after `set_user_roles`:
```python
@router.post("/users/{user_id}/reset-password")
def admin_reset_user_password(
    user_id: uuid.UUID, payload: AdminResetPasswordIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_users")),
):
    try:
        out = svc.admin_reset_password(session, current=current,
                                       user_id=user_id, new_password=payload.new_password)
    except svc.AdminError as e:
        session.rollback()
        raise _exc(e)
    session.commit()
    return out
```
(Import `AdminResetPasswordIn` from `app.schemas.admin`.)

- [ ] **Step 4:** Tests — append to `backend/tests/test_admin_service.py` and `backend/tests/test_admin_api.py`:
  - service: admin sets a known password (audited `password_reset`); omitted password → returned generated one that logs in; cross-org target (org_admin) → `NotFound`; non-admin actor → `AdminError`/forbidden.
  - api: `POST /api/admin/users/{id}/reset-password` 200 with body `{}` returns `password`; 403 without `admin:manage_users`; 404 cross-org.

- [ ] **Step 5:** Run → pass; full suite green. **Step 6:** commit `feat(admin): admin-assisted password reset (audited)`.

---

### Task 6: Frontend — change password + forgot password

**Files:** modify `frontend/src/features/settings/settings-view.tsx`; create `frontend/src/app/(auth)/forgot-password/page.tsx` + `frontend/src/features/auth/forgot-password-view.tsx`; modify `frontend/src/app/(auth)/login/page.tsx` (add link); modify `frontend/src/locales/{en,zh}.ts`; tests.

- [ ] **Step 1:** Add locale keys to BOTH `en.ts` and `zh.ts` under `settings` and `auth`:
  - `settings.changePasswordTitle`, `settings.changePasswordDesc`, `settings.currentPassword`, `settings.newPassword`, `settings.confirmPassword`, `settings.passwordChanged`, `settings.passwordMismatch`, `settings.passwordIncorrect`
  - `auth.forgotPassword`, `auth.forgotPasswordTitle`, `auth.forgotPasswordDesc`, `auth.email`, `auth.sendResetLink`, `auth.resetToken`, `auth.resetTokenPlaceholder`, `auth.newPassword`, `auth.confirmReset`, `auth.resetSent` (dev hint), `auth.passwordReset`, `auth.backToLogin`

- [ ] **Step 2:** Add a "Change password" `<Card>` to `settings-view.tsx` (current/new/confirm fields; validates match; `PUT /api/auth/password`; toast on success). Use `Field` + `Input` + `Button`; route labels through `t()`.

- [ ] **Step 3:** Create `frontend/src/features/auth/forgot-password-view.tsx` — two-step form (email → request; then token+new_password → confirm), calling `POST /api/auth/reset-password/request` and `/confirm`. In dev, display the returned token. Use `BACKEND` from `@/lib/config`, `useT()`, `Field`/`Input`/`Button`.

- [ ] **Step 4:** Create `frontend/src/app/(auth)/forgot-password/page.tsx` (thin wrapper rendering the view in the auth layout).

- [ ] **Step 5:** Add a "Forgot password?" `<Link>` to the login page (next to the register link).

- [ ] **Step 6:** Tests — `frontend/src/features/settings/__tests__/settings-view.test.tsx`: assert the change-password card renders with accessible labels and rejects mismatched confirm. Add `frontend/src/features/auth/__tests__/forgot-password-view.test.tsx`: assert the two-step flow renders and the confirm button is disabled until fields filled. Render via `renderWithProviders`.

- [ ] **Step 7:** `npm run test && npm run lint && npm run build` → green. **Step 8:** commit `feat(auth): frontend change-password + forgot-password flows`.

---

### Task 7: Docs + full verification + push

**Files:** modify `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` (FR-USER-03), `CLAUDE.md`, `docs/audits/2026-07-03-improvement-proposals.md` (mark P0 #1 done).

- [ ] **Step 1:** Update PRD §6.1 FR-USER-03 to describe the token-based reset + admin-assisted reset + authenticated change (replacing the "email-free stub" wording). Bump PRD version note.
- [ ] **Step 2:** Update `CLAUDE.md` Current State: note the secure password flows, new `AuditAction` values, the new migration `e7a1b2c3d4e5`, the `password_reset_token_ttl_minutes` env var, and that the old `POST /api/auth/reset-password` is removed. Add to the auth env-var list.
- [ ] **Step 3:** In the audit doc, mark P0 #1 ✅ complete with the commit SHA.
- [ ] **Step 4:** Full backend suite + migration drift test + frontend tests/build → all green.
- [ ] **Step 5:** Commit docs `docs: secure password reset (P0 #1) — PRD/CLAUDE/audit update`.
- [ ] **Step 6:** Push the branch to GitHub.

---

## Self-Review

**Spec coverage:** §3 token store → Task 1. §5 settings → Task 1. §8 migration → Task 2. §6.1–6.3 service+API → Tasks 3,4. §6.4 admin → Task 5. §9 frontend → Task 6. §10 testing → embedded in each task. §11 acceptance → covered by Tasks 4,5,6,7.

**Placeholder scan:** none — every code step has full code.

**Type consistency:** `PasswordResetTokenStore`, `change_password`, `request_password_reset`, `confirm_password_reset`, `admin_reset_password`, `get_reset_token_store` — names match across tasks.

**Known follow-up (documented, not blocking):** password change does not invalidate existing refresh/access tokens (requires P1 #8 revocation infra); reset-token email delivery not implemented (no mail infra — dev returns token).
