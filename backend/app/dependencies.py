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
    InMemoryRevokedTokenStore,
    RedisRefreshTokenStore,
    RedisPasswordResetTokenStore,
    RedisRevokedTokenStore,
    RefreshTokenStore,
    RevokedTokenStore,
    decode_access_token,
)
from app.db.session import get_session
from app.models.auth import User
from app.models.enums import UserStatus
from app.services.auth import (
    InMemoryLockoutStore,
    LockoutStore,
    RedisLockoutStore,
    load_user_perms,
    load_user_roles,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

_store: RefreshTokenStore | None = None
_lockout: LockoutStore | None = None
_reset_store: "RedisPasswordResetTokenStore | None" = None
_revoked_store: RevokedTokenStore | None = None


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


def get_reset_token_store() -> RedisPasswordResetTokenStore:
    global _reset_store
    if _reset_store is None:
        _reset_store = RedisPasswordResetTokenStore(settings.redis_url)
    return _reset_store


def get_revoked_store() -> RevokedTokenStore:
    global _revoked_store
    if _revoked_store is None:
        _revoked_store = RedisRevokedTokenStore(settings.redis_url)
    return _revoked_store


@dataclass
class CurrentUser:
    user: User
    org_id: uuid.UUID
    roles: list[str]
    perms: list[str]


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
    revoked_store: RevokedTokenStore = Depends(get_revoked_store),
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
    # #8: reject revoked (logged-out) access tokens by jti before their natural expiry.
    jti = claims.get("jti")
    if jti and revoked_store.is_revoked(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="token revoked",
                            headers={"WWW-Authenticate": "Bearer"})
    user = session.get(User, uuid.UUID(claims["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    # #8: reject disabled users immediately (status change takes effect on the next request,
    # no need to revoke individual tokens).
    if user.status == UserStatus.disabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="account disabled")
    org_id = uuid.UUID(claims["org_id"])
    # #8: load roles+perms fresh from the DB rather than trusting token claims, so a
    # role revocation takes effect immediately (not up to 60 min stale).
    roles = load_user_roles(session, user.id, org_id)
    perms = load_user_perms(session, user.id, org_id)
    return CurrentUser(user=user, org_id=org_id, roles=roles, perms=perms)


def get_active_org_id(current: CurrentUser = Depends(get_current_user)) -> uuid.UUID:
    return current.org_id


def require_permission(code: str) -> Callable:
    def _dep(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if code not in current.perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"missing permission: {code}")
        return current
    return _dep
