"""Auth service: registration, login (with lockout), refresh, logout."""

import uuid
from dataclasses import dataclass
from datetime import timedelta
import time

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    PasswordResetTokenStore,
    RefreshTokenStore,
    RevokedTokenStore,
    create_access_token,
    decode_access_token,
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
from app.models.enums import AuditAction, OrgKind, RoleName, UserStatus
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
        key = email.lower()
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    def is_locked(self, email):
        return self._counts.get(email.lower(), 0) >= self.threshold

    def reset(self, email):
        self._counts.pop(email.lower(), None)


class RedisLockoutStore(LockoutStore):
    def __init__(self, redis_url: str) -> None:
        import redis

        self._redis = redis.from_url(redis_url, socket_connect_timeout=2)
        self._prefix = "loginfail:"

    def _key(self, email: str) -> str:
        return f"{self._prefix}{email.lower()}"

    def record_failure(self, email):
        key = self._key(email)
        count = self._redis.incr(key)
        if count == 1:
            self._redis.expire(key, settings.login_lockout_window_minutes * 60)
        return count

    def is_locked(self, email):
        v = self._redis.get(self._key(email))
        if v is None:
            return False
        return int(v) >= settings.login_lockout_threshold

    def reset(self, email):
        self._redis.delete(self._key(email))


def load_user_roles(session: Session, user_id: uuid.UUID, org_id: uuid.UUID) -> list[str]:
    rows = session.execute(
        select(Role.name)
        .join(OrganizationMembership, OrganizationMembership.role_id == Role.id)
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == org_id,
        )
    ).scalars().all()
    return [r.value for r in rows]


def load_user_perms(session: Session, user_id: uuid.UUID, org_id: uuid.UUID) -> list[str]:
    rows = session.execute(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(OrganizationMembership, OrganizationMembership.role_id == RolePermission.role_id)
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == org_id,
        )
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
                  display_name: str | None,
                  refresh_store: RefreshTokenStore) -> tuple[User, AuthTokens]:
    email = email.lower().strip()
    existing = session.execute(select(User).filter_by(email=email)).scalar_one_or_none()
    if existing is not None:
        raise AuthError("email already registered", status_code=409)

    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
        status=UserStatus.active,
    )
    session.add(user)
    session.flush()

    org = Organization(
        name=f"{display_name or email}'s space",
        slug=f"personal-{user.id.hex[:8]}",
        kind=OrgKind.personal,
    )
    session.add(org)
    session.flush()

    learner_role = session.execute(
        select(Role).filter_by(name=RoleName.individual_learner)
    ).scalar_one()
    session.add(OrganizationMembership(
        user_id=user.id, organization_id=org.id, role_id=learner_role.id,
    ))
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
        threshold = getattr(lockout_store, "threshold", None) or settings.login_lockout_threshold
        if count >= threshold:
            raise AuthError("too many failed attempts; try later", status_code=429)
        raise AuthError("invalid credentials", status_code=401)

    if user.status != UserStatus.active:
        raise AuthError("account disabled", status_code=403)

    lockout_store.reset(email)
    org_id = user.default_organization_id
    tokens = issue_tokens(session, user, org_id, refresh_store)
    log_audit(
        session, action=AuditAction.login, actor_id=user.id,
        organization_id=org_id, entity_type="user", entity_id=str(user.id),
    )
    return user, tokens


def refresh_tokens(session: Session, refresh_store: RefreshTokenStore,
                   refresh_token: str) -> AuthTokens:
    data = refresh_store.load(refresh_token)
    if data is None:
        raise AuthError("invalid or expired refresh token", status_code=401)
    # #7: reuse detection — a token that was already rotated is being replayed
    # (likely stolen). Revoke the entire family so every descendant of the
    # original login dies, forcing re-auth everywhere.
    if data.get("rotated"):
        refresh_store.revoke_family(data["family_id"])
        log_audit(
            session, action=AuditAction.logout, actor_id=uuid.UUID(data["user_id"]),
            organization_id=uuid.UUID(data["org_id"]),
            entity_type="refresh_token", entity_id=data["family_id"],
            details={"reason": "refresh_token_reuse"},
        )
        raise AuthError("refresh token reuse detected", status_code=401)
    user_id = uuid.UUID(data["user_id"])
    org_id = uuid.UUID(data["org_id"])
    user = session.get(User, user_id)
    if user is None or user.status != UserStatus.active:
        refresh_store.delete(refresh_token)
        raise AuthError("account disabled", status_code=403)
    new_refresh = refresh_store.rotate(
        refresh_token, user_id=user.id, org_id=org_id, ttl_seconds=_refresh_ttl()
    )
    roles = load_user_roles(session, user.id, org_id)
    perms = load_user_perms(session, user.id, org_id)
    access = create_access_token(user_id=user.id, org_id=org_id, roles=roles, perms=perms)
    return AuthTokens(access_token=access, refresh_token=new_refresh)


def logout(refresh_store: RefreshTokenStore, revoked_store: RevokedTokenStore,
           refresh_token: str, access_token: str | None) -> None:
    """Invalidate the refresh token AND the access token (#8). The access token's
    jti is added to the revocation list with a TTL equal to its remaining lifetime,
    so it's rejected on the next request but the list self-prunes at natural expiry."""
    refresh_store.delete(refresh_token)
    if not access_token:
        return
    try:
        claims = decode_access_token(access_token)
    except jwt.PyJWTError:
        return  # already expired/invalid — nothing to revoke
    jti = claims.get("jti")
    exp = claims.get("exp")
    if not jti or not exp:
        return
    ttl = max(0, int(exp) - int(time.time()))
    if ttl > 0:
        revoked_store.revoke(jti, ttl)


# ---- P0 #1: secure password change + reset ----

def change_password(session: Session, *, user: User, current_password: str,
                    new_password: str) -> None:
    """Authenticated password change — requires proof of the current password."""
    if not user.password_hash or not verify_password(current_password, user.password_hash):
        raise AuthError("incorrect current password", status_code=401)
    user.password_hash = hash_password(new_password)
    session.flush()
    log_audit(
        session, action=AuditAction.password_change, actor_id=user.id,
        organization_id=user.default_organization_id,
        entity_type="user", entity_id=str(user.id),
    )


def request_password_reset(session: Session, *, email: str,
                           reset_store: PasswordResetTokenStore,
                           lockout_store: LockoutStore) -> str | None:
    """Issue a single-use reset token for a known email.

    Returns the token if the email maps to a user, else None. Always returns
    None-ish for unknown emails without raising, so the API can answer 200
    uniformly (no email enumeration). Per-email throttling via the lockout store.
    """
    email = email.lower().strip()
    if lockout_store.is_locked(email):
        raise AuthError("too many attempts; try later", status_code=429)
    user = session.execute(select(User).filter_by(email=email)).scalar_one_or_none()
    if user is None:
        # throttle even on misses so an attacker can't enumerate freely
        lockout_store.record_failure(email)
        return None
    token = reset_store.issue(
        user.id,
        ttl_seconds=int(
            timedelta(minutes=settings.password_reset_token_ttl_minutes).total_seconds()
        ),
    )
    lockout_store.reset(email)
    log_audit(
        session, action=AuditAction.password_reset, actor_id=None,
        organization_id=user.default_organization_id,
        entity_type="user", entity_id=str(user.id), details={"phase": "requested"},
    )
    return token


def confirm_password_reset(session: Session, *, token: str, new_password: str,
                           reset_store: PasswordResetTokenStore) -> User:
    """Consume a single-use reset token and set the new password."""
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
    log_audit(
        session, action=AuditAction.password_reset, actor_id=user.id,
        organization_id=user.default_organization_id,
        entity_type="user", entity_id=str(user.id), details={"phase": "confirmed"},
    )
    return user
