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
    RedisPasswordResetTokenStore,
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
_reset_store: "RedisPasswordResetTokenStore | None" = None


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
