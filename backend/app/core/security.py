"""Security primitives: password hashing, JWT, refresh-token storage."""

import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Protocol

import jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.bcrypt_rounds
)


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
        self._redis.setex(self._key(token), ttl_seconds, json.dumps(_entry(user_id, org_id)))

    def load(self, token):
        raw = self._redis.get(self._key(token))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        return json.loads(raw)

    def delete(self, token):
        self._redis.delete(self._key(token))

    def rotate(self, old, *, user_id, org_id, ttl_seconds):
        self.delete(old)
        new = generate_refresh_token()
        self.store(new, user_id, org_id, ttl_seconds)
        return new
