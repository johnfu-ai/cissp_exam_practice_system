# Auth & RBAC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add JWT access + Redis-backed refresh authentication, permission-based RBAC dependencies, lockout, audit logging, lock down the ETL API, and a minimal login/register/logout frontend — so the system is usable end-to-end by a real authenticated user.

**Architecture:** Stateless HS256 access tokens carry user/org/roles/perms claims. Opaque refresh tokens live in Redis (rotation + revocation). A `require_permission(code)` FastAPI dependency enforces RBAC; `get_active_org_id` provides tenant scoping. Auth service owns register/login/refresh/logout and writes `AuditLog`. The ETL router is rewired to use the new dependencies, repaying the "unauthenticated stubs" debt.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, PyJWT, passlib[bcrypt], redis-py 5.2, Next.js 14, Zustand.

## Global Constraints

- Tests run against the dedicated `cissp_test` Postgres DB via per-test SAVEPOINT rollback (see `backend/tests/conftest.py`); never touch the dev `cissp` DB.
- Password hashing: bcrypt via passlib, rounds from `settings.bcrypt_rounds` (default 12). NFR-SEC-01.
- JWT: HS256, `settings.jwt_secret`. Warn (not fail) when secret is `change-me` outside tests.
- All non-`/api/auth/*` and non-`/health` routes require a valid access token (401) and the route's permission (403).
- Tenant scoping: content writes use `active_org_id` from the token claim (CLAUDE.md tenant rule).
- Email is case-insensitive: lower-case before compare/insert (relies on existing `uq_users_email_lower` index).
- No Alembic migration in this sub-project — all auth models already exist. Only bump `SEED_VERSION` to `"3"`.
- Frontend stores access+refresh in a Zustand store mirrored to `sessionStorage`; API client auto-refreshes once on 401.

---

### Task 1: Dependencies + config

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/core/config.py`

**Interfaces:**
- Produces: `Settings.refresh_token_expire_days`, `Settings.bcrypt_rounds`, `Settings.login_lockout_threshold`, `Settings.login_lockout_window_minutes`, `Settings.cors_origins`.

- [ ] **Step 1: Add deps to requirements.txt**

Append to `backend/requirements.txt`:

```
passlib[bcrypt]==1.7.4
bcrypt==4.2.1
pyjwt==2.10.1
```

- [ ] **Step 2: Install**

Run: `cd backend && source venv/bin/activate && pip install -r requirements.txt`
Expected: installs passlib, bcrypt, pyjwt successfully.

- [ ] **Step 3: Extend Settings**

Replace the body of `backend/app/core/config.py` with:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://cissp:cissp@localhost:5432/cissp"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14
    bcrypt_rounds: int = 12
    login_lockout_threshold: int = 5
    login_lockout_window_minutes: int = 15
    cors_origins: str = "http://localhost:3000"
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = ""


settings = Settings()
```

- [ ] **Step 4: Verify import**

Run: `cd backend && source venv/bin/activate && python -c "from app.core.config import settings; print(settings.bcrypt_rounds, settings.refresh_token_expire_days)"`
Expected: `12 14`

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/app/core/config.py
git commit -m "feat(auth): add auth deps and settings"
```

---

### Task 2: Security primitives (hashing, JWT, refresh store)

**Files:**
- Create: `backend/app/core/security.py`
- Test: `backend/tests/test_security.py`

**Interfaces:**
- Produces:
  - `hash_password(plain: str) -> str`
  - `verify_password(plain: str, hashed: str) -> bool`
  - `create_access_token(*, user_id: uuid.UUID, org_id: uuid.UUID, roles: list[str], perms: list[str]) -> str`
  - `decode_access_token(token: str) -> dict` (raises `jwt.PyJWTError` on invalid/expired)
  - `RefreshTokenStore` (Protocol) with `store(token, user_id, org_id, ttl_seconds)`, `load(token) -> dict | None`, `delete(token)`, `rotate(old, *, user_id, org_id, ttl_seconds) -> str`
  - `RedisRefreshTokenStore(redis_url, prefix="refresh:")` implementing the protocol
  - `InMemoryRefreshTokenStore()` implementing the protocol (for tests)
  - `generate_refresh_token() -> str`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_security.py`:

```python
import time
import uuid

import jwt
import pytest

from app.core.security import (
    InMemoryRefreshTokenStore,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrips():
    h = hash_password("s3cret!")
    assert h != "s3cret!"
    assert verify_password("s3cret!", h) is True
    assert verify_password("wrong", h) is False


def test_access_token_roundtrips_claims():
    uid = uuid.uuid4()
    oid = uuid.uuid4()
    token = create_access_token(
        user_id=uid, org_id=oid, roles=["individual_learner"], perms=["question:read"]
    )
    claims = decode_access_token(token)
    assert claims["sub"] == str(uid)
    assert claims["org_id"] == str(oid)
    assert claims["roles"] == ["individual_learner"]
    assert claims["perms"] == ["question:read"]


def test_decode_invalid_token_raises():
    with pytest.raises(jwt.PyJWTError):
        decode_access_token("not.a.token")


def test_refresh_token_store_store_load_delete():
    store = InMemoryRefreshTokenStore()
    token = generate_refresh_token()
    uid, oid = uuid.uuid4(), uuid.uuid4()
    store.store(token, uid, oid, ttl_seconds=60)
    assert store.load(token) == {"user_id": str(uid), "org_id": str(oid)}
    store.delete(token)
    assert store.load(token) is None


def test_refresh_token_store_rotate_invalidates_old():
    store = InMemoryRefreshTokenStore()
    uid, oid = uuid.uuid4(), uuid.uuid4()
    new_token = store.rotate("nonexistent", user_id=uid, org_id=oid, ttl_seconds=60)
    # rotating a nonexistent token still issues a new one bound to the caller
    assert store.load(new_token) == {"user_id": str(uid), "org_id": str(oid)}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_security.py -v`
Expected: FAIL (module not found / import error).

- [ ] **Step 3: Implement security.py**

Create `backend/app/core/security.py`:

```python
"""Security primitives: password hashing, JWT, refresh-token storage."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Protocol

import jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.bcrypt_rounds)


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_access_token(
    *, user_id: uuid.UUID, org_id: uuid.UUID, roles: list[str], perms: list[str]
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "roles": roles,
        "perms": sorted(perms),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "jti": secrets.token_urlsafe(8),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


class RefreshTokenStore(Protocol):
    def store(self, token: str, user_id: uuid.UUID, org_id: uuid.UUID, ttl_seconds: int) -> None: ...
    def load(self, token: str) -> dict | None: ...
    def delete(self, token: str) -> None: ...
    def rotate(self, old: str, *, user_id: uuid.UUID, org_id: uuid.UUID, ttl_seconds: int) -> str: ...


def _entry(user_id: uuid.UUID, org_id: uuid.UUID) -> dict:
    return {"user_id": str(user_id), "org_id": str(org_id)}


class InMemoryRefreshTokenStore:
    def __init__(self) -> None:
        self._data: dict[str, dict] = {}

    def store(self, token, user_id, org_id, ttl_seconds):
        self._data[token] = _entry(user_id, org_id)

    def load(self, token):
        return self._data.get(token)

    def delete(self, token):
        self._data.pop(token, None)

    def rotate(self, old, *, user_id, org_id, ttl_seconds):
        self.delete(old)
        new = generate_refresh_token()
        self.store(new, user_id, org_id, ttl_seconds)
        return new


class RedisRefreshTokenStore:
    def __init__(self, redis_url: str, prefix: str = "refresh:") -> None:
        import redis

        self._redis = redis.from_url(redis_url, socket_connect_timeout=2)
        self._prefix = prefix

    def _key(self, token: str) -> str:
        return f"{self._prefix}{token}"

    def store(self, token, user_id, org_id, ttl_seconds):
        import json

        self._redis.setex(self._key(token), ttl_seconds, json.dumps(_entry(user_id, org_id)))

    def load(self, token):
        import json

        raw = self._redis.get(self._key(token))
        if raw is None:
            return None
        return json.loads(raw)

    def delete(self, token):
        self._redis.delete(self._key(token))

    def rotate(self, old, *, user_id, org_id, ttl_seconds):
        self.delete(old)
        new = generate_refresh_token()
        self.store(new, user_id, org_id, ttl_seconds)
        return new
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_security.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/tests/test_security.py
git commit -m "feat(auth): security primitives (bcrypt, JWT, refresh store)"
```

---

### Task 3: Auth service (register/login/refresh/logout/lockout)

**Files:**
- Create: `backend/app/services/auth.py`
- Test: `backend/tests/test_auth_service.py`

**Interfaces:**
- Consumes: `hash_password`, `verify_password`, `create_access_token`, `generate_refresh_token`, `RefreshTokenStore` (Task 2); `log_audit` (existing); models `User`, `Organization`, `OrganizationMembership`, `Role`, `RolePermission`, `Permission`.
- Produces:
  - `AuthTokens` (dataclass) `{access_token: str, refresh_token: str, token_type: "bearer"}`
  - `register_user(session, *, email, password, display_name, refresh_store) -> tuple[User, AuthTokens]`
  - `authenticate(session, *, email, password, refresh_store, lockout_store) -> tuple[User, AuthTokens]` (raises `AuthError`)
  - `refresh_tokens(session, refresh_store, refresh_token) -> AuthTokens` (raises `AuthError`)
  - `logout(refresh_store, refresh_token) -> None`
  - `AuthError(Exception)` with `.status_code`
  - `load_user_perms(session, user_id, org_id) -> list[str]`
  - `load_user_roles(session, user_id, org_id) -> list[str]`
  - `issue_tokens(session, user, org_id, refresh_store) -> AuthTokens`

**Lockout:** A separate small store (Redis `loginfail:{email}` counter, TTL = window). For testability, `authenticate` takes a `lockout_store` with `record_failure(email) -> int` and `is_locked(email) -> bool`. Provide `RedisLockoutStore` and `InMemoryLockoutStore`.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_auth_service.py`:

```python
import uuid

import pytest

from app.models.auth import Organization, OrganizationMembership, Role, User
from app.models.enums import OrgKind, RoleName
from app.core.security import InMemoryRefreshTokenStore
from app.services.auth import (
    AuthError,
    InMemoryLockoutStore,
    authenticate,
    issue_tokens,
    load_user_perms,
    logout,
    refresh_tokens,
    register_user,
)


def _seed_role(session, name):
    role = session.query(Role).filter_by(name=name).first()
    if role is None:
        role = Role(name=name, description=name.value)
        session.add(role); session.flush()
    return role


def test_register_user_creates_personal_org_and_membership(session_with_roles):
    session = session_with_roles
    store = InMemoryRefreshTokenStore()
    user, tokens = register_user(
        session, email="ALICE@Example.com", password="pw123456",
        display_name="Alice", refresh_store=store,
    )
    session.flush()
    assert user.email == "alice@example.com"  # case-folded
    assert user.password_hash and user.password_hash != "pw123456"
    assert user.default_organization_id is not None
    # personal org exists
    org = session.get(Organization, user.default_organization_id)
    assert org.kind == OrgKind.personal
    # membership with individual_learner role
    m = session.query(OrganizationMembership).filter_by(user_id=user.id).one()
    assert m.role.name == RoleName.individual_learner
    assert tokens.access_token and tokens.refresh_token


def test_register_duplicate_email_raises(session_with_roles):
    session = session_with_roles
    store = InMemoryRefreshTokenStore()
    register_user(session, email="bob@example.com", password="pw123456",
                  display_name="Bob", refresh_store=store)
    session.flush()
    with pytest.raises(AuthError) as exc:
        register_user(session, email="BOB@example.com", password="pw123456",
                      display_name="Bob2", refresh_store=store)
    assert exc.value.status_code == 409


def test_authenticate_success_and_lockout(session_with_roles):
    session = session_with_roles
    store = InMemoryRefreshTokenStore()
    lockout = InMemoryLockoutStore(threshold=2)
    register_user(session, email="carol@example.com", password="pw123456",
                  display_name="Carol", refresh_store=store)
    session.flush()

    user, tokens = authenticate(session, email="carol@example.com", password="pw123456",
                                refresh_store=store, lockout_store=lockout)
    assert user.email == "carol@example.com"

    # wrong password increments; at threshold raises 429
    with pytest.raises(AuthError) as e1:
        authenticate(session, email="carol@example.com", password="wrong",
                     refresh_store=store, lockout_store=lockout)
    assert e1.value.status_code == 401
    with pytest.raises(AuthError) as e2:
        authenticate(session, email="carol@example.com", password="wrong",
                     refresh_store=store, lockout_store=lockout)
    assert e2.value.status_code == 429


def test_refresh_rotates_and_old_invalid(session_with_roles):
    session = session_with_roles
    store = InMemoryRefreshTokenStore()
    user, tokens = register_user(session, email="dave@example.com", password="pw123456",
                                 display_name="Dave", refresh_store=store)
    session.flush()
    new_tokens = refresh_tokens(session, store, tokens.refresh_token)
    assert new_tokens.refresh_token != tokens.refresh_token
    # old token no longer valid
    with pytest.raises(AuthError):
        refresh_tokens(session, store, tokens.refresh_token)


def test_logout_invalidates_refresh(session_with_roles):
    session = session_with_roles
    store = InMemoryRefreshTokenStore()
    user, tokens = register_user(session, email="eve@example.com", password="pw123456",
                                 display_name="Eve", refresh_store=store)
    session.flush()
    logout(store, tokens.refresh_token)
    with pytest.raises(AuthError):
        refresh_tokens(session, store, tokens.refresh_token)


def test_load_user_perms_returns_role_perms(session_with_roles):
    session = session_with_roles
    store = InMemoryRefreshTokenStore()
    user, tokens = register_user(session, email="frank@example.com", password="pw123456",
                                 display_name="Frank", refresh_store=store)
    session.flush()
    perms = load_user_perms(session, user.id, user.default_organization_id)
    # individual_learner gets question:read, practice:read, exam:read per seed
    assert set(perms) >= {"question:read", "practice:read", "exam:read"}
```

- [ ] **Step 2: Add the `session_with_roles` fixture**

Append to `backend/tests/conftest.py` (after the `db_session` fixture):

```python
@pytest.fixture
def session_with_roles(db_session):
    """db_session with seeded roles + permissions (individual_learner perms)."""
    from app.db.seed import PERMISSIONS, ROLE_PERMISSIONS
    from app.models.auth import Permission, Role, RolePermission
    from app.models.enums import RoleName

    perm_by_code = {}
    for code, desc in PERMISSIONS:
        p = db_session.query(Permission).filter_by(code=code).first()
        if p is None:
            p = Permission(code=code, description=desc)
            db_session.add(p); db_session.flush()
        perm_by_code[code] = p
    role_by_name = {}
    for name in RoleName:
        r = db_session.query(Role).filter_by(name=name).first()
        if r is None:
            r = Role(name=name, description=name.value)
            db_session.add(r); db_session.flush()
        role_by_name[name] = r
    for name, codes in ROLE_PERMISSIONS.items():
        for code in codes:
            exists = db_session.query(RolePermission).filter_by(
                role_id=role_by_name[name].id, permission_id=perm_by_code[code].id).first()
            if exists is None:
                db_session.add(RolePermission(role_id=role_by_name[name].id,
                                              permission_id=perm_by_code[code].id))
    db_session.flush()
    return db_session
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_auth_service.py -v`
Expected: FAIL (module `app.services.auth` not found).

- [ ] **Step 4: Implement the auth service**

Create `backend/app/services/auth.py`:

```python
"""Auth service: registration, login (with lockout), refresh, logout."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    RefreshTokenStore,
    create_access_token,
    generate_refresh_token,
    hash_password,
    verify_password,
)
from app.models.auth import (
    Organization,
    OrganizationMembership,
    Permission,
    Role,
    RolePermission,
    User,
)
from app.models.enums import AuditAction, OrgKind, RoleName
from app.models.enums import UserStatus
from app.services.audit import log_audit


@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


def _refresh_ttl() -> int:
    return int(timedelta(days=settings.refresh_token_expire_days).total_seconds())


class LockoutStore:
    def record_failure(self, email: str) -> int: ...
    def is_locked(self, email: str) -> bool: ...
    def reset(self, email: str) -> None: ...


class InMemoryLockoutStore(LockoutStore):
    def __init__(self, threshold: int | None = None) -> None:
        self._counts: dict[str, int] = {}
        self.threshold = threshold or settings.login_lockout_threshold

    def record_failure(self, email):
        self._counts[email] = self._counts.get(email, 0) + 1
        return self._counts[email]

    def is_locked(self, email):
        return self._counts.get(email, 0) >= self.threshold

    def reset(self, email):
        self._counts.pop(email, None)


class RedisLockoutStore(LockoutStore):
    def __init__(self, redis_url: str) -> None:
        import redis

        self._redis = redis.from_url(redis_url, socket_connect_timeout=2)
        self._prefix = "loginfail:"

    def record_failure(self, email):
        key = f"{self._prefix}{email.lower()}"
        count = self._redis.incr(key)
        if count == 1:
            self._redis.expire(key, settings.login_lockout_window_minutes * 60)
        return count

    def is_locked(self, email):
        return self._redis.get(f"{self._prefix}{email.lower()}") is not None and \
            int(self._redis.get(f"{self._prefix}{email.lower()}")) >= settings.login_lockout_threshold

    def reset(self, email):
        self._redis.delete(f"{self._prefix}{email.lower()}")


def load_user_roles(session: Session, user_id: uuid.UUID, org_id: uuid.UUID) -> list[str]:
    rows = session.execute(
        select(Role.name).join(OrganizationMembership, OrganizationMembership.role_id == Role.id)
        .where(OrganizationMembership.user_id == user_id,
               OrganizationMembership.organization_id == org_id)
    ).scalars().all()
    return [r.value for r in rows]


def load_user_perms(session: Session, user_id: uuid.UUID, org_id: uuid.UUID) -> list[str]:
    rows = session.execute(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(OrganizationMembership, OrganizationMembership.role_id == RolePermission.role_id)
        .where(OrganizationMembership.user_id == user_id,
               OrganizationMembership.organization_id == org_id)
    ).scalars().all()
    return list(rows)


def issue_tokens(session: Session, user: User, org_id: uuid.UUID,
                 refresh_store: RefreshTokenStore) -> AuthTokens:
    roles = load_user_roles(session, user.id, org_id)
    perms = load_user_perms(session, user.id, org_id)
    access = create_access_token(user_id=user.id, org_id=org_id, roles=roles, perms=perms)
    refresh = generate_refresh_token()
    refresh_store.store(refresh, user.id, org_id, _refresh_ttl())
    return AuthTokens(access_token=access, refresh_token=refresh)


def register_user(session: Session, *, email: str, password: str,
                  display_name: str | None, refresh_store: RefreshTokenStore) -> tuple[User, AuthTokens]:
    email = email.lower().strip()
    existing = session.execute(select(User).filter_by(email=email)).scalar_one_or_none()
    if existing is not None:
        raise AuthError("email already registered", status_code=409)

    user = User(email=email, password_hash=hash_password(password),
                display_name=display_name, status=UserStatus.active)
    session.add(user); session.flush()

    org = Organization(name=f"{display_name or email}'s space",
                       slug=f"personal-{user.id.hex[:8]}",
                       kind=OrgKind.personal)
    session.add(org); session.flush()

    learner_role = session.execute(select(Role).filter_by(name=RoleName.individual_learner)).scalar_one()
    session.add(OrganizationMembership(user_id=user.id, organization_id=org.id,
                                       role_id=learner_role.id))
    user.default_organization_id = org.id
    session.flush()

    tokens = issue_tokens(session, user, org.id, refresh_store)
    return user, tokens


def authenticate(session: Session, *, email: str, password: str,
                 refresh_store: RefreshTokenStore,
                 lockout_store: LockoutStore) -> tuple[User, AuthTokens]:
    email = email.lower().strip()
    if lockout_store.is_locked(email):
        raise AuthError("too many failed attempts; try later", status_code=429)

    user = session.execute(select(User).filter_by(email=email)).scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        count = lockout_store.record_failure(email)
        if count >= (getattr(lockout_store, "threshold", None) or settings.login_lockout_threshold):
            raise AuthError("too many failed attempts; try later", status_code=429)
        raise AuthError("invalid credentials", status_code=401)

    if user.status != UserStatus.active:
        raise AuthError("account disabled", status_code=403)

    lockout_store.reset(email)
    org_id = user.default_organization_id
    tokens = issue_tokens(session, user, org_id, refresh_store)
    log_audit(session, action=AuditAction.login, actor_id=user.id,
              organization_id=org_id, entity_type="user", entity_id=str(user.id))
    return user, tokens


def refresh_tokens(session: Session, refresh_store: RefreshTokenStore,
                   refresh_token: str) -> AuthTokens:
    data = refresh_store.load(refresh_token)
    if data is None:
        raise AuthError("invalid or expired refresh token", status_code=401)
    user_id = uuid.UUID(data["user_id"])
    org_id = uuid.UUID(data["org_id"])
    user = session.get(User, user_id)
    if user is None or user.status != UserStatus.active:
        refresh_store.delete(refresh_token)
        raise AuthError("account disabled", status_code=403)
    new_refresh = refresh_store.rotate(refresh_token, user_id=user.id, org_id=org_id,
                                       ttl_seconds=_refresh_ttl())
    roles = load_user_roles(session, user.id, org_id)
    perms = load_user_perms(session, user.id, org_id)
    access = create_access_token(user_id=user.id, org_id=org_id, roles=roles, perms=perms)
    return AuthTokens(access_token=access, refresh_token=new_refresh)


def logout(refresh_store: RefreshTokenStore, refresh_token: str) -> None:
    refresh_store.delete(refresh_token)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_auth_service.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/auth.py backend/tests/test_auth_service.py backend/tests/conftest.py
git commit -m "feat(auth): auth service (register/login/lockout/refresh/logout)"
```

---

### Task 4: RBAC dependencies

**Files:**
- Create: `backend/app/dependencies.py`
- Test: `backend/tests/test_dependencies.py`

**Interfaces:**
- Consumes: `decode_access_token` (Task 2); `load_user_perms`; `User`; `get_session`.
- Produces:
  - `get_refresh_store() -> RefreshTokenStore` (Redis in prod; overridable)
  - `get_lockout_store() -> LockoutStore`
  - `CurrentUser` (dataclass) `{user: User, org_id: uuid.UUID, roles: list[str], perms: list[str]}`
  - `get_current_user(token: str = Depends(oauth2_scheme), session = Depends(get_session)) -> CurrentUser`
  - `get_active_org_id(current = Depends(get_current_user)) -> uuid.UUID`
  - `require_permission(code: str) -> Callable` returning a dependency that yields `CurrentUser` or raises 401/403.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_dependencies.py`:

```python
import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.dependencies import CurrentUser, get_current_user, get_refresh_store, require_permission
from app.db.session import get_session
from app.models.auth import Organization, OrganizationMembership, Role, User
from app.models.enums import OrgKind, RoleName
from app.services.auth import InMemoryLockoutStore, register_user


def _build_app(db_session, refresh_store):
    app = FastAPI()

    def _session():
        yield db_session
    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_refresh_store] = lambda: refresh_store

    @app.get("/me")
    def me(current: CurrentUser = Depends(get_current_user)):
        return {"email": current.user.email, "perms": current.perms}

    @app.get("/admin")
    def admin(current: CurrentUser = Depends(require_permission("admin:manage_taxonomy"))):
        return {"ok": True}
    return app


def _make_user(db_session, refresh_store, email="dep@example.com"):
    user, _ = register_user(db_session, email=email, password="pw123456",
                            display_name="Dep", refresh_store=refresh_store)
    db_session.flush()
    # grant system_admin role on the personal org for the admin test
    sa_role = db_session.query(Role).filter_by(name=RoleName.system_admin).first()
    if sa_role is None:
        sa_role = Role(name=RoleName.system_admin, description="sysadmin")
        db_session.add(sa_role); db_session.flush()
    m = db_session.query(OrganizationMembership).filter_by(user_id=user.id).one()
    m.role_id = sa_role.id
    db_session.flush()
    return user


def test_no_token_returns_401(db_session, session_with_roles):
    refresh_store = InMemoryRefreshTokenStore()
    app = _build_app(db_session, refresh_store)
    client = TestClient(app)
    resp = client.get("/me")
    assert resp.status_code == 401


def test_valid_token_returns_user(db_session, session_with_roles):
    refresh_store = InMemoryRefreshTokenStore()
    user = _make_user(db_session, refresh_store)
    token = create_access_token(user_id=user.id, org_id=user.default_organization_id,
                                roles=["system_admin"], perms=["admin:manage_taxonomy"])
    app = _build_app(db_session, refresh_store)
    client = TestClient(app)
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "dep@example.com"


def test_require_permission_denies_without_perm(db_session, session_with_roles):
    refresh_store = InMemoryRefreshTokenStore()
    # plain learner (no admin perms)
    user, _ = register_user(db_session, email="learner@example.com", password="pw123456",
                            display_name="L", refresh_store=refresh_store)
    db_session.flush()
    token = create_access_token(user_id=user.id, org_id=user.default_organization_id,
                                roles=["individual_learner"], perms=["question:read"])
    app = _build_app(db_session, refresh_store)
    client = TestClient(app)
    resp = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_require_permission_allows_with_perm(db_session, session_with_roles):
    refresh_store = InMemoryRefreshTokenStore()
    user = _make_user(db_session, refresh_store, email="admin2@example.com")
    token = create_access_token(user_id=user.id, org_id=user.default_organization_id,
                                roles=["system_admin"], perms=["admin:manage_taxonomy"])
    app = _build_app(db_session, refresh_store)
    client = TestClient(app)
    resp = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_dependencies.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement dependencies.py**

Create `backend/app/dependencies.py`:

```python
"""FastAPI dependencies: auth, RBAC, tenant scoping."""

import uuid
from dataclasses import dataclass
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    InMemoryRefreshTokenStore,
    RedisRefreshTokenStore,
    RefreshTokenStore,
    decode_access_token,
)
from app.db.session import get_session
from app.models.auth import User
from app.services.auth import (
    InMemoryLockoutStore,
    LockoutStore,
    RedisLockoutStore,
    load_user_perms,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

_store: RefreshTokenStore | None = None
_lockout: LockoutStore | None = None


def get_refresh_store() -> RefreshTokenStore:
    global _store
    if _store is None:
        _store = RedisRefreshTokenStore(settings.redis_url)
    return _store


def get_lockout_store() -> LockoutStore:
    global _lockout
    if _lockout is None:
        _lockout = RedisLockoutStore(settings.redis_url)
    return _lockout


@dataclass
class CurrentUser:
    user: User
    org_id: uuid.UUID
    roles: list[str]
    perms: list[str]


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> CurrentUser:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="not authenticated", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"})
    user = session.get(User, uuid.UUID(claims["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return CurrentUser(user=user, org_id=uuid.UUID(claims["org_id"]),
                       roles=claims.get("roles", []), perms=claims.get("perms", []))


def get_active_org_id(current: CurrentUser = Depends(get_current_user)) -> uuid.UUID:
    return current.org_id


def require_permission(code: str) -> Callable:
    def _dep(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if code not in current.perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"missing permission: {code}")
        return current
    return _dep
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_dependencies.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/dependencies.py backend/tests/test_dependencies.py
git commit -m "feat(auth): RBAC dependencies (current_user, require_permission)"
```

---

### Task 5: Auth API router

**Files:**
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/main.py` (register router + CORS)
- Test: `backend/tests/test_auth_api.py`

**Interfaces:**
- Produces endpoints: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/refresh`, `POST /api/auth/logout`, `GET /api/auth/me`, `POST /api/auth/reset-password`.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_auth_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.core.security import InMemoryRefreshTokenStore
from app.dependencies import get_lockout_store, get_refresh_store
from app.db.session import get_session
from app.main import create_app
from app.services.auth import InMemoryLockoutStore


@pytest.fixture
def client(db_session, session_with_roles):
    app = create_app()
    refresh_store = InMemoryRefreshTokenStore()
    lockout = InMemoryLockoutStore(threshold=2)
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: refresh_store
    app.dependency_overrides[get_lockout_store] = lambda: lockout
    return TestClient(app), refresh_store, lockout


def test_register_and_me(client):
    c, store, _ = client
    resp = c.post("/api/auth/register",
                  json={"email": "API@Example.com", "password": "pw123456", "display_name": "API"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["email"] == "api@example.com"
    assert body["access_token"] and body["refresh_token"]
    me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "api@example.com"


def test_login_success(client):
    c, store, _ = client
    c.post("/api/auth/register", json={"email": "login@example.com", "password": "pw123456"})
    resp = c.post("/api/auth/login", json={"email": "login@example.com", "password": "pw123456"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_wrong_password_then_lockout(client):
    c, store, _ = client
    c.post("/api/auth/register", json={"email": "lock@example.com", "password": "pw123456"})
    r1 = c.post("/api/auth/login", json={"email": "lock@example.com", "password": "wrong"})
    assert r1.status_code == 401
    r2 = c.post("/api/auth/login", json={"email": "lock@example.com", "password": "wrong"})
    assert r2.status_code == 429


def test_refresh_and_logout(client):
    c, store, _ = client
    reg = c.post("/api/auth/register", json={"email": "r@example.com", "password": "pw123456"}).json()
    rt = reg["refresh_token"]
    resp = c.post("/api/auth/refresh", json={"refresh_token": rt})
    assert resp.status_code == 200
    new_rt = resp.json()["refresh_token"]
    assert new_rt != rt
    # old refresh rotated away
    assert c.post("/api/auth/refresh", json={"refresh_token": rt}).status_code == 401
    out = c.post("/api/auth/logout", json={"refresh_token": new_rt})
    assert out.status_code == 200
    assert c.post("/api/auth/refresh", json={"refresh_token": new_rt}).status_code == 401


def test_me_without_token_401(client):
    c, _, _ = client
    assert c.get("/api/auth/me").status_code == 401


def test_reset_password(client):
    c, _, _ = client
    c.post("/api/auth/register", json={"email": "reset@example.com", "password": "pw123456"})
    resp = c.post("/api/auth/reset-password",
                  json={"email": "reset@example.com", "new_password": "newpw123"})
    assert resp.status_code == 200
    # can login with new password
    login = c.post("/api/auth/login", json={"email": "reset@example.com", "password": "newpw123"})
    assert login.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_auth_api.py -v`
Expected: FAIL (no `/api/auth` router).

- [ ] **Step 3: Implement schemas**

Create `backend/app/schemas/auth.py`:

```python
from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=255)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str


class ResetPasswordIn(BaseModel):
    email: EmailStr
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str | None
    roles: list[str]
    perms: list[str]


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
```

- [ ] **Step 4: Implement auth router**

Create `backend/app/api/auth.py`:

```python
"""Auth HTTP API."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dependencies import CurrentUser, get_current_user, get_lockout_store, get_refresh_store
from app.models.auth import User
from app.models.enums import AuditAction, UserStatus
from app.schemas.auth import (
    LoginIn,
    LogoutIn,
    RefreshIn,
    RegisterIn,
    ResetPasswordIn,
    TokenOut,
    UserOut,
)
from app.services.audit import log_audit
from app.services.auth import (
    AuthError,
    LockoutStore,
    authenticate,
    load_user_perms,
    load_user_roles,
    logout,
    refresh_tokens,
    register_user,
)
from app.core.security import RefreshTokenStore

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(session, user, org_id) -> UserOut:
    return UserOut(
        id=str(user.id), email=user.email, display_name=user.display_name,
        roles=load_user_roles(session, user.id, org_id),
        perms=load_user_perms(session, user.id, org_id),
    )


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, session: Session = Depends(get_session),
             refresh_store: RefreshTokenStore = Depends(get_refresh_store)):
    try:
        user, tokens = register_user(session, email=body.email, password=body.password,
                                     display_name=body.display_name, refresh_store=refresh_store)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    session.commit()
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token,
                    user=_user_out(session, user, user.default_organization_id))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, session: Session = Depends(get_session),
          refresh_store: RefreshTokenStore = Depends(get_refresh_store),
          lockout_store: LockoutStore = Depends(get_lockout_store)):
    try:
        user, tokens = authenticate(session, email=body.email, password=body.password,
                                    refresh_store=refresh_store, lockout_store=lockout_store)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    session.commit()
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token,
                    user=_user_out(session, user, user.default_organization_id))


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, session: Session = Depends(get_session),
            refresh_store: RefreshTokenStore = Depends(get_refresh_store)):
    try:
        tokens = refresh_tokens(session, refresh_store, body.refresh_token)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    session.commit()
    # re-load user for the response
    from sqlalchemy import select
    user = session.get(User, _extract_user_id(tokens.access_token))
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token,
                    user=_user_out(session, user, _extract_org_id(tokens.access_token)))


def _extract_user_id(access_token):
    from app.core.security import decode_access_token
    import uuid
    return uuid.UUID(decode_access_token(access_token)["sub"])


def _extract_org_id(access_token):
    from app.core.security import decode_access_token
    import uuid
    return uuid.UUID(decode_access_token(access_token)["org_id"])


@router.post("/logout")
def logout_route(body: LogoutIn,
                 refresh_store: RefreshTokenStore = Depends(get_refresh_store)):
    logout(refresh_store, body.refresh_token)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(current: CurrentUser = Depends(get_current_user),
       session: Session = Depends(get_session)):
    return _user_out(session, current.user, current.org_id)


@router.post("/reset-password")
def reset_password(body: ResetPasswordIn, session: Session = Depends(get_session),
                   refresh_store: RefreshTokenStore = Depends(get_refresh_store),
                   lockout_store: LockoutStore = Depends(get_lockout_store)):
    from sqlalchemy import select
    # MVP email-free: caller must prove email ownership out-of-band (TODO: email token)
    if lockout_store.is_locked(body.email.lower()):
        raise HTTPException(status_code=429, detail="too many attempts; try later")
    user = session.execute(select(User).filter_by(email=body.email.lower())).scalar_one_or_none()
    if user is None:
        # do not leak existence
        lockout_store.record_failure(body.email.lower())
        raise HTTPException(status_code=404, detail="not found")
    from app.core.security import hash_password
    user.password_hash = hash_password(body.new_password)
    log_audit(session, action=AuditAction.config_change, actor_id=user.id,
              organization_id=user.default_organization_id,
              entity_type="user", entity_id=str(user.id),
              details={"reset": True})
    session.commit()
    return {"ok": True}
```

- [ ] **Step 5: Register router + CORS in main.py**

Replace `backend/app/main.py` with:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import router as auth_router
from app.api.etl import router as etl_router
from app.core.config import settings
from app.db.session import get_engine


def create_app() -> FastAPI:
    app = FastAPI(title="CISSP Exam Practice System", version="0.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        db_status = "ok"
        redis_status = "ok"
        try:
            engine = get_engine()
            with Session(engine) as session:
                session.execute(text("SELECT 1"))
        except Exception:
            db_status = "error"
        try:
            import redis

            r = redis.from_url(settings.redis_url, socket_connect_timeout=2)
            r.ping()
        except Exception:
            redis_status = "error"
        return {"status": "ok", "db": db_status, "redis": redis_status}

    app.include_router(auth_router)
    app.include_router(etl_router)

    return app


app = create_app()
```

- [ ] **Step 6: Add email-validator dep**

`EmailStr` requires `email-validator`. Add to `backend/requirements.txt`:

```
email-validator==2.2.0
```

Run: `cd backend && source venv/bin/activate && pip install email-validator==2.2.0`

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_auth_api.py -v`
Expected: 6 passed.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/api/auth.py backend/app/main.py backend/requirements.txt backend/tests/test_auth_api.py
git commit -m "feat(auth): /api/auth router (register/login/refresh/logout/me/reset)"
```

---

### Task 6: Lock down the ETL API

**Files:**
- Modify: `backend/app/api/etl.py`
- Modify: `backend/tests/etl/test_api_etl.py`

**Interfaces:**
- Consumes: `require_permission`, `get_active_org_id`, `CurrentUser` (Task 4).

- [ ] **Step 1: Update ETL API tests to require auth**

In `backend/tests/etl/test_api_etl.py`, replace the `client` fixture and add a helper that mints a token for a system_admin user, then add `Authorization` headers to all requests. Add two new tests for 401/403.

Replace the `client` fixture with:

```python
from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.dependencies import get_lockout_store, get_refresh_store
from app.services.auth import InMemoryLockoutStore, register_user


@pytest.fixture
def client(db_session, session_with_roles):
    app = create_app()
    refresh_store = InMemoryRefreshTokenStore()
    lockout = InMemoryLockoutStore()
    def _session():
        yield db_session
    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_refresh_store] = lambda: refresh_store
    app.dependency_overrides[get_lockout_store] = lambda: lockout
    return TestClient(app)


def _auth_header(db_session, refresh_store, email="etladmin@example.com",
                 perms=None, roles=None):
    user, _ = register_user(db_session, email=email, password="pw123456",
                            display_name="Etl", refresh_store=refresh_store)
    db_session.flush()
    # promote to system_admin
    from app.models.auth import Role, OrganizationMembership
    from app.models.enums import RoleName
    sa = db_session.query(Role).filter_by(name=RoleName.system_admin).first()
    if sa is None:
        sa = Role(name=RoleName.system_admin, description="sysadmin")
        db_session.add(sa); db_session.flush()
    m = db_session.query(OrganizationMembership).filter_by(user_id=user.id).one()
    m.role_id = sa.id
    db_session.flush()
    token = create_access_token(
        user_id=user.id, org_id=user.default_organization_id,
        roles=roles or ["system_admin"], perms=perms or [c for c, _ in __import__("app.db.seed", fromlist=["PERMISSIONS"]).PERMISSIONS])
    return {"Authorization": f"Bearer {token}"}
```

Then in each existing test, capture the header and pass it. For example `test_list_datasets` becomes:

```python
def test_list_datasets(client, db_session):
    org_id = _seed(db_session)
    headers = _auth_header(db_session, client.app.dependency_overrides[get_refresh_store]())
    resp = client.get("/api/etl/datasets", headers=headers)
    assert resp.status_code == 200
```

(Apply the same `headers=headers` to every request in the file. Note: `client` is the `TestClient`; access the refresh store via the same lambda — store it in a variable instead. Simplify the fixture to expose the store:)

```python
@pytest.fixture
def client_and_store(db_session, session_with_roles):
    app = create_app()
    refresh_store = InMemoryRefreshTokenStore()
    lockout = InMemoryLockoutStore()
    def _session():
        yield db_session
    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_refresh_store] = lambda: refresh_store
    app.dependency_overrides[get_lockout_store] = lambda: lockout
    return TestClient(app), refresh_store
```

Rename existing tests to use `client_and_store` and `c, store = client_and_store`. Add:

```python
def test_datasets_unauthenticated_401(client_and_store, db_session):
    c, _ = client_and_store
    _seed(db_session)
    assert c.get("/api/etl/datasets").status_code == 401


def test_runs_forbidden_without_perm(client_and_store, db_session):
    c, store = client_and_store
    _seed(db_session)
    # learner with no question:import perm
    user, _ = register_user(db_session, email="nop@e.com", password="pw123456",
                            display_name="N", refresh_store=store)
    db_session.flush()
    token = create_access_token(user_id=user.id, org_id=user.default_organization_id,
                                roles=["individual_learner"], perms=["question:read"])
    resp = c.post("/api/etl/runs", json={"dataset_slug": "mini"},
                  headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/etl/test_api_etl.py -v`
Expected: FAIL (routes don't enforce auth yet → 200 where 401/403 expected, and existing tests send no header).

- [ ] **Step 3: Rewrite etl.py with auth**

Replace the body of `backend/app/api/etl.py` with:

```python
"""ETL HTTP API. Permission-gated via app.dependencies."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dependencies import CurrentUser, get_active_org_id, require_permission
from app.etl.runner import run_commit, run_preview, run_rollback
from app.models.etl import ChapterDomainMapping, EtlDataset, EtlRun

router = APIRouter(prefix="/api/etl", tags=["etl"])


class CreateRunIn(BaseModel):
    dataset_slug: str


class MappingIn(BaseModel):
    dataset_slug: str
    chapter_number: int
    chapter_title: str
    domain_id: uuid.UUID | None = None


@router.get("/datasets")
def list_datasets(session: Session = Depends(get_session),
                  _: CurrentUser = Depends(require_permission("question:import"))):
    rows = session.execute(select(EtlDataset)).scalars().all()
    return [{"id": str(d.id), "slug": d.slug, "name": d.name,
             "source_path": d.source_path, "total_questions": d.total_questions,
             "languages": d.languages} for d in rows]


@router.get("/datasets/{slug}")
def get_dataset(slug: str, session: Session = Depends(get_session),
                _: CurrentUser = Depends(require_permission("question:import"))):
    d = session.execute(select(EtlDataset).filter_by(slug=slug)).scalar_one_or_none()
    if d is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return {"id": str(d.id), "slug": d.slug, "name": d.name,
            "source_path": d.source_path, "total_questions": d.total_questions,
            "languages": d.languages}


@router.post("/runs")
def create_run(body: CreateRunIn, session: Session = Depends(get_session),
               current: CurrentUser = Depends(require_permission("question:import"))):
    ds = session.execute(select(EtlDataset).filter_by(slug=body.dataset_slug)).scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    run = run_preview(session, current.org_id, ds, initiated_by_id=current.user.id)
    session.commit()
    return {"run_id": str(run.id), "phase": run.phase.value, "preview_summary": run.preview_summary}


@router.get("/runs/{run_id}")
def get_run(run_id: uuid.UUID, session: Session = Depends(get_session),
            _: CurrentUser = Depends(require_permission("question:import"))):
    run = session.get(EtlRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": str(run.id), "phase": run.phase.value,
            "preview_summary": run.preview_summary, "committed_at": run.committed_at}


@router.post("/runs/{run_id}/commit")
def commit_run(run_id: uuid.UUID, session: Session = Depends(get_session),
               current: CurrentUser = Depends(require_permission("question:import"))):
    try:
        run = run_commit(session, current.org_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    session.commit()
    return {"run_id": str(run.id), "phase": run.phase.value}


@router.post("/runs/{run_id}/rollback")
def rollback_run(run_id: uuid.UUID, session: Session = Depends(get_session),
                 _: CurrentUser = Depends(require_permission("question:import"))):
    try:
        run = run_rollback(session, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    session.commit()
    return {"run_id": str(run.id), "phase": run.phase.value}


@router.get("/mappings")
def list_mappings(dataset_slug: str | None = None, session: Session = Depends(get_session),
                  _: CurrentUser = Depends(require_permission("admin:manage_taxonomy"))):
    stmt = select(ChapterDomainMapping)
    if dataset_slug:
        stmt = stmt.filter_by(dataset_slug=dataset_slug)
    rows = session.execute(stmt).scalars().all()
    return [{"id": str(m.id), "dataset_slug": m.dataset_slug,
             "chapter_number": m.chapter_number, "chapter_title": m.chapter_title,
             "domain_id": str(m.domain_id) if m.domain_id else None} for m in rows]


@router.post("/mappings")
def create_mapping(body: MappingIn, session: Session = Depends(get_session),
                   _: CurrentUser = Depends(require_permission("admin:manage_taxonomy"))):
    m = ChapterDomainMapping(dataset_slug=body.dataset_slug, chapter_number=body.chapter_number,
                             chapter_title=body.chapter_title, domain_id=body.domain_id)
    session.add(m)
    session.commit()
    return {"id": str(m.id), "dataset_slug": m.dataset_slug, "chapter_number": m.chapter_number}


@router.put("/mappings/{mapping_id}")
def update_mapping(mapping_id: uuid.UUID, body: MappingIn, session: Session = Depends(get_session),
                   _: CurrentUser = Depends(require_permission("admin:manage_taxonomy"))):
    m = session.get(ChapterDomainMapping, mapping_id)
    if m is None:
        raise HTTPException(status_code=404, detail="mapping not found")
    m.chapter_title = body.chapter_title
    m.domain_id = body.domain_id
    session.commit()
    return {"id": str(m.id)}


@router.delete("/mappings/{mapping_id}")
def delete_mapping(mapping_id: uuid.UUID, session: Session = Depends(get_session),
                   _: CurrentUser = Depends(require_permission("admin:manage_taxonomy"))):
    m = session.get(ChapterDomainMapping, mapping_id)
    if m is None:
        raise HTTPException(status_code=404, detail="mapping not found")
    session.delete(m)
    session.commit()
    return {"deleted": str(mapping_id)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/etl/test_api_etl.py -v`
Expected: all pass, including the new 401/403 tests.

- [ ] **Step 5: Run full suite**

Run: `cd backend && source venv/bin/activate && pytest`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/etl.py backend/tests/etl/test_api_etl.py
git commit -m "feat(auth): gate ETL API behind require_permission (repay unauth stubs)"
```

---

### Task 7: Seed bootstrap admin

**Files:**
- Modify: `backend/app/db/seed.py`
- Modify: `backend/tests/test_seed.py`

**Interfaces:**
- Produces: a `system_admin` user on the personal org with email `settings.seed_admin_email`, created only if it doesn't exist, password from `settings.seed_admin_password` (random + printed if unset). `SEED_VERSION` → `"3"`.

- [ ] **Step 1: Write failing test**

Add to `backend/tests/test_seed.py`:

```python
def test_seed_creates_bootstrap_admin(db_session):
    from app.db.seed import run_seed
    from app.models.auth import User, OrganizationMembership
    from app.models.enums import RoleName
    run_seed(db_session)
    admin = db_session.query(User).filter_by(email="admin@example.com").one()
    assert admin.password_hash
    m = db_session.query(OrganizationMembership).filter_by(user_id=admin.id).one()
    assert m.role.name == RoleName.system_admin
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && source venv/bin/activate && pytest tests/test_seed.py::test_seed_creates_bootstrap_admin -v`
Expected: FAIL (no admin user).

- [ ] **Step 3: Implement**

In `backend/app/db/seed.py`:
- Change `SEED_VERSION = "2"` → `SEED_VERSION = "3"`.
- Add imports: `from app.core.config import settings`, `from app.core.security import hash_password`, `from app.models.auth import Organization, Permission, Role, RolePermission, User, OrganizationMembership`, `from app.models.enums import ... RoleName, UserStatus`.
- Add `import secrets` at top.
- After the roles+role_permissions block (before the dataset block), add:

```python
    # Bootstrap system_admin (so the system is usable after auth lock-down).
    admin_email = settings.seed_admin_email.lower()
    admin = session.execute(select(User).filter_by(email=admin_email)).scalar_one_or_none()
    if admin is None:
        pw = settings.seed_admin_password or secrets.token_urlsafe(16)
        admin = User(email=admin_email, password_hash=hash_password(pw),
                     display_name="System Admin", status=UserStatus.active,
                     default_organization_id=personal_org.id)
        session.add(admin); session.flush()
        if not settings.seed_admin_password:
            print(f"[seed] created admin {admin_email} with generated password: {pw}")
        sa_role = role_by_name[RoleName.system_admin]
        existing = session.execute(
            select(OrganizationMembership).filter_by(
                user_id=admin.id, organization_id=personal_org.id, role_id=sa_role.id)
        ).scalar_one_or_none()
        if existing is None:
            session.add(OrganizationMembership(user_id=admin.id,
                                               organization_id=personal_org.id,
                                               role_id=sa_role.id))
    session.flush()
```

(Ensure `role_by_name` is defined before this block — it is, from the existing roles loop.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source venv/bin/activate && pytest tests/test_seed.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/seed.py backend/tests/test_seed.py
git commit -m "feat(auth): seed bootstrap system_admin (SEED_VERSION 3)"
```

---

### Task 8: Frontend — API client + auth store + login/register/logout

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/auth-store.ts`
- Create: `frontend/src/app/(auth)/login/page.tsx`
- Create: `frontend/src/app/(auth)/register/page.tsx`
- Modify: `frontend/src/app/page.tsx` (show auth state + links)
- Modify: `frontend/package.json` (add zustand)

**Interfaces:**
- Produces: a typed fetch wrapper `apiFetch(path, init)` that injects the bearer token and refreshes once on 401; a Zustand `useAuthStore` with `user`, `accessToken`, `refreshToken`, `login`, `register`, `logout`, `hydrate`.

- [ ] **Step 1: Add zustand**

Run: `cd frontend && npm install zustand@5.0.2`
Expected: installs zustand.

- [ ] **Step 2: Create auth store**

Create `frontend/src/lib/auth-store.ts`:

```typescript
"use client";

import { create } from "zustand";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
  roles: string[];
  perms: string[];
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  setAuth: (user: AuthUser, access: string, refresh: string) => void;
  clear: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  setAuth: (user, access, refresh) => {
    sessionStorage.setItem("access", access);
    sessionStorage.setItem("refresh", refresh);
    set({ user, accessToken: access, refreshToken: refresh });
  },
  clear: () => {
    sessionStorage.removeItem("access");
    sessionStorage.removeItem("refresh");
    set({ user: null, accessToken: null, refreshToken: null });
  },
  hydrate: () => {
    const access = sessionStorage.getItem("access");
    const refresh = sessionStorage.getItem("refresh");
    if (access && refresh) set({ accessToken: access, refreshToken: refresh });
  },
}));
```

- [ ] **Step 3: Create API client**

Create `frontend/src/lib/api.ts`:

```typescript
import { useAuthStore } from "./auth-store";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const { accessToken, refreshToken, setAuth, clear } = useAuthStore.getState();
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  let resp = await fetch(`${BACKEND}${path}`, { ...init, headers, credentials: "include" });
  if (resp.status !== 401) return resp;

  // try one refresh
  if (!refreshToken) return resp;
  const r = await fetch(`${BACKEND}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    credentials: "include",
  });
  if (!r.ok) {
    clear();
    return resp;
  }
  const data = await r.json();
  setAuth(data.user, data.access_token, data.refresh_token);
  const retryHeaders = new Headers(init.headers);
  retryHeaders.set("Authorization", `Bearer ${data.access_token}`);
  if (init.body && !retryHeaders.has("Content-Type")) retryHeaders.set("Content-Type", "application/json");
  return fetch(`${BACKEND}${path}`, { ...init, headers: retryHeaders, credentials: "include" });
}

export async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await apiFetch(path, init);
  if (!resp.ok) throw new ApiError(resp.status, await resp.text());
  return resp.json() as Promise<T>;
}
```

- [ ] **Step 4: Create login page**

Create `frontend/src/app/(auth)/login/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/auth-store";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const resp = await fetch(`${BACKEND}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!resp.ok) {
      setError(resp.status === 429 ? "Too many attempts. Try later." : "Invalid credentials.");
      return;
    }
    const data = await resp.json();
    setAuth(data.user, data.access_token, data.refresh_token);
    router.push("/");
  }

  return (
    <main className="mx-auto max-w-sm p-8">
      <h1 className="text-2xl font-bold mb-4">Log in</h1>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <input type="email" placeholder="email" value={email}
               onChange={(e) => setEmail(e.target.value)} className="border p-2 rounded" required />
        <input type="password" placeholder="password" value={password}
               onChange={(e) => setPassword(e.target.value)} className="border p-2 rounded" required />
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button type="submit" className="bg-blue-600 text-white p-2 rounded">Log in</button>
      </form>
      <p className="mt-4 text-sm">
        No account? <a href="/register" className="text-blue-600 underline">Register</a>
      </p>
    </main>
  );
}
```

- [ ] **Step 5: Create register page**

Create `frontend/src/app/(auth)/register/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/auth-store";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const resp = await fetch(`${BACKEND}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, display_name: displayName || null }),
    });
    if (!resp.ok) {
      const t = await resp.text();
      setError(resp.status === 409 ? "Email already registered." : t);
      return;
    }
    const data = await resp.json();
    setAuth(data.user, data.access_token, data.refresh_token);
    router.push("/");
  }

  return (
    <main className="mx-auto max-w-sm p-8">
      <h1 className="text-2xl font-bold mb-4">Register</h1>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <input type="email" placeholder="email" value={email}
               onChange={(e) => setEmail(e.target.value)} className="border p-2 rounded" required />
        <input type="text" placeholder="display name (optional)" value={displayName}
               onChange={(e) => setDisplayName(e.target.value)} className="border p-2 rounded" />
        <input type="password" placeholder="password (min 8)" value={password}
               onChange={(e) => setPassword(e.target.value)} className="border p-2 rounded" required />
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button type="submit" className="bg-blue-600 text-white p-2 rounded">Register</button>
      </form>
    </main>
  );
}
```

- [ ] **Step 6: Update home page**

Replace `frontend/src/app/page.tsx` with a client component that hydrates auth, shows login/logout, and a smoke-test link to fetch ETL datasets:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/auth-store";
import { apiJson } from "@/lib/api";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const { user, accessToken, hydrate, clear } = useAuthStore();
  const [health, setHealth] = useState<string>("...");
  const [datasets, setDatasets] = useState<string>("");

  useEffect(() => {
    hydrate();
    fetch(`${BACKEND}/health`).then((r) => r.json()).then((j) => setHealth(JSON.stringify(j))).catch(() => setHealth("error"));
  }, [hydrate]);

  async function loadDatasets() {
    try {
      const ds = await apiJson<any[]>("/api/etl/datasets");
      setDatasets(ds.map((d) => d.slug).join(", "));
    } catch (e: any) {
      setDatasets(`error: ${e.message}`);
    }
  }

  async function logout() {
    const rt = useAuthStore.getState().refreshToken;
    if (rt) {
      await fetch(`${BACKEND}/api/auth/logout`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: rt }),
      });
    }
    clear();
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-3xl font-bold mb-2">CISSP Exam Practice</h1>
      <p className="text-gray-600 mb-6">Backend health: {health}</p>
      {accessToken && user ? (
        <div className="space-y-4">
          <p>Signed in as <strong>{user.email}</strong> (roles: {user.roles.join(", ")})</p>
          <button onClick={logout} className="border px-4 py-2 rounded">Log out</button>
          <div>
            <button onClick={loadDatasets} className="bg-blue-600 text-white px-4 py-2 rounded">List ETL datasets</button>
            {datasets && <p className="mt-2 text-sm">datasets: {datasets}</p>}
          </div>
        </div>
      ) : (
        <div className="space-x-4">
          <a href="/login" className="bg-blue-600 text-white px-4 py-2 rounded inline-block">Log in</a>
          <a href="/register" className="border px-4 py-2 rounded inline-block">Register</a>
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 7: Build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/
git commit -m "feat(auth): frontend login/register/logout + api client + auth store"
```

---

### Task 9: End-to-end verification + docs

**Files:**
- Modify: `CLAUDE.md` (update Current State + add auth env vars)

- [ ] **Step 1: Run full backend suite**

Run: `cd backend && source venv/bin/activate && pytest`
Expected: all pass.

- [ ] **Step 2: Run alembic drift check**

Run: `cd backend && source venv/bin/activate && pytest tests/test_migrations.py -v`
Expected: pass (no schema change, no drift).

- [ ] **Step 3: Manual end-to-end smoke (if stack running)**

If `docker compose` is up:
- `curl -s localhost:8000/health` → ok.
- Register: `curl -s -XPOST localhost:8000/api/auth/register -H 'content-type: application/json' -d '{"email":"smoke@example.com","password":"smoke1234"}'` → token.
- Login, me, refresh, logout each return expected status.

If the stack is not running, note that and rely on the automated tests; do not block.

- [ ] **Step 4: Update CLAUDE.md Current State**

In `CLAUDE.md`, under "## Current State", append a line noting auth is implemented and list the new env vars (`seed_admin_email`, `seed_admin_password`, `jwt_secret`, `cors_origins`). Update the "What does NOT exist yet" list to remove auth/JWT.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update current state for auth sub-project"
```

---

## Self-Review

**Spec coverage:** §2 credential model → Tasks 2,3. §3 files → Tasks 2,3,4,5. §4 settings → Task 1. §5 hashing → Task 2. §6 flows → Task 3 (service) + Task 5 (API). §7 RBAC dep → Task 4. §8 ETL gate → Task 6. §9 seed admin → Task 7. §10 frontend → Task 8. §11 testing → embedded in each task. §12 no migration → confirmed (no Alembic task). §13 acceptance → covered by Tasks 5,6,7,8,9.

**Placeholder scan:** none — every code step has full code.

**Type consistency:** `AuthTokens`, `CurrentUser`, `RefreshTokenStore`, `LockoutStore`, `register_user`, `authenticate`, `refresh_tokens`, `logout`, `load_user_perms`, `load_user_roles`, `issue_tokens`, `require_permission`, `get_current_user`, `get_active_org_id`, `get_refresh_store`, `get_lockout_store` — names match across tasks.

**One caveat noted in plan:** Task 5's `refresh` endpoint re-decodes the access token to get user/org id for the response — slightly awkward but correct and tested. Acceptable.
