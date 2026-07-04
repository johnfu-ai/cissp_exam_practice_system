"""Security primitives: password hashing, JWT, refresh-token storage."""

import json
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Protocol

import bcrypt
import jwt

from app.core.config import settings

# bcrypt operates on a 72-byte password limit; passlib truncated silently, so we
# match that to avoid a behavior change for the schema's max_length=128 inputs
# (bcrypt 4.x raises ValueError past 72 bytes).
_BCRYPT_MAX_BYTES = 72


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(
        plain.encode("utf-8")[:_BCRYPT_MAX_BYTES],
        bcrypt.gensalt(rounds=settings.bcrypt_rounds),
    ).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    # checkpw is constant-time. Malformed/legacy hashes return False, never raise.
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8")[:_BCRYPT_MAX_BYTES], hashed.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


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
    def revoke_family(self, family_id: str) -> None: ...


def _entry(user_id: uuid.UUID, org_id: uuid.UUID, family_id: str, rotated: bool = False) -> dict:
    return {"user_id": str(user_id), "org_id": str(org_id),
            "family_id": family_id, "rotated": rotated}


class InMemoryRefreshTokenStore:
    """#7: refresh tokens carry a family_id (shared across rotations from one
    login). Rotation marks the old token `rotated` (kept, not deleted) so a
    replayed/stolen token is detectable; on reuse the whole family is revoked."""

    def __init__(self) -> None:
        self._tokens: dict[str, dict] = {}
        self._families: dict[str, set[str]] = {}

    def store(self, token, user_id, org_id, ttl_seconds):
        family_id = generate_refresh_token()
        self._tokens[token] = _entry(user_id, org_id, family_id)
        self._families.setdefault(family_id, set()).add(token)

    def load(self, token):
        return self._tokens.get(token)

    def delete(self, token):
        entry = self._tokens.pop(token, None)
        if entry is not None:
            fam = self._families.get(entry["family_id"])
            if fam is not None:
                fam.discard(token)
                if not fam:
                    self._families.pop(entry["family_id"], None)

    def rotate(self, old, *, user_id, org_id, ttl_seconds):
        entry = self._tokens.get(old)
        if entry is None:
            # caller didn't load first / token expired — issue a fresh-family token
            new = generate_refresh_token()
            self.store(new, user_id, org_id, ttl_seconds)
            return new
        family_id = entry["family_id"]
        entry["rotated"] = True  # keep so a later reuse is detectable
        new = generate_refresh_token()
        self._tokens[new] = _entry(user_id, org_id, family_id)
        self._families.setdefault(family_id, set()).add(new)
        return new

    def revoke_family(self, family_id):
        for token in self._families.pop(family_id, set()):
            self._tokens.pop(token, None)


class RedisRefreshTokenStore:
    def __init__(self, redis_url: str, prefix: str = "refresh:",
                 family_prefix: str = "refresh_family:") -> None:
        import redis

        self._redis = redis.from_url(redis_url, socket_connect_timeout=2)
        self._prefix = prefix
        self._family_prefix = family_prefix

    def _key(self, token: str) -> str:
        return f"{self._prefix}{token}"

    def _fkey(self, family_id: str) -> str:
        return f"{self._family_prefix}{family_id}"

    def store(self, token, user_id, org_id, ttl_seconds):
        family_id = generate_refresh_token()
        self._redis.setex(self._key(token), ttl_seconds,
                          json.dumps(_entry(user_id, org_id, family_id)))
        self._redis.sadd(self._fkey(family_id), token)
        self._redis.expire(self._fkey(family_id), ttl_seconds)

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
        raw = self._redis.get(self._key(old))
        if raw is None:
            new = generate_refresh_token()
            self.store(new, user_id, org_id, ttl_seconds)
            return new
        if isinstance(raw, bytes):
            raw = raw.decode()
        entry = json.loads(raw)
        family_id = entry["family_id"]
        # re-write the old token marked `rotated` (TTL = current refresh lifetime)
        # so a replay is detectable until natural expiry.
        entry["rotated"] = True
        self._redis.setex(self._key(old), ttl_seconds, json.dumps(entry))
        new = generate_refresh_token()
        self._redis.setex(self._key(new), ttl_seconds,
                          json.dumps(_entry(user_id, org_id, family_id)))
        self._redis.sadd(self._fkey(family_id), new)
        self._redis.expire(self._fkey(family_id), ttl_seconds)
        return new

    def revoke_family(self, family_id):
        fkey = self._fkey(family_id)
        members = self._redis.smembers(fkey)
        if members:
            keys = [self._key(m.decode() if isinstance(m, bytes) else m) for m in members]
            if keys:
                self._redis.delete(*keys)
        self._redis.delete(fkey)


class PasswordResetTokenStore(Protocol):
    """Single-use, short-lived password-reset tokens (TTL-bounded)."""

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
        # pop = single-use: a second consume returns None
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
        token = generate_refresh_token()
        self._redis.setex(
            self._key(token), ttl_seconds, json.dumps({"user_id": str(user_id)})
        )
        return token

    def consume(self, token):
        # GETDEL is atomic -> single-use even under concurrency
        raw = self._redis.getdel(self._key(token))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        return uuid.UUID(json.loads(raw)["user_id"])

    def delete(self, token):
        self._redis.delete(self._key(token))


class RevokedTokenStore(Protocol):
    """Access-token revocation list for logout (#8). Each entry is a `jti` with a
    TTL equal to the token's remaining lifetime, so the list self-prunes as
    tokens pass their natural expiry — it can't grow unbounded."""

    def revoke(self, jti: str, ttl_seconds: int) -> None: ...
    def is_revoked(self, jti: str) -> bool: ...


class InMemoryRevokedTokenStore:
    def __init__(self) -> None:
        self._data: dict[str, float] = {}  # jti -> expiry epoch

    def revoke(self, jti, ttl_seconds):
        self._data[jti] = time.time() + ttl_seconds

    def is_revoked(self, jti):
        exp = self._data.get(jti)
        if exp is None:
            return False
        if time.time() >= exp:
            self._data.pop(jti, None)  # lazy prune
            return False
        return True


class RedisRevokedTokenStore:
    def __init__(self, redis_url: str, prefix: str = "revoked:") -> None:
        import redis

        self._redis = redis.from_url(redis_url, socket_connect_timeout=2)
        self._prefix = prefix

    def _key(self, jti: str) -> str:
        return f"{self._prefix}{jti}"

    def revoke(self, jti, ttl_seconds):
        self._redis.setex(self._key(jti), ttl_seconds, "1")

    def is_revoked(self, jti):
        return bool(self._redis.exists(self._key(jti)))


class RateLimiter(Protocol):
    """Fixed-window per-key counter (e.g., per-IP login attempts, #10). `allow`
    returns True if the request is under the limit, False if it should be rejected."""

    def allow(self, key: str, *, limit: int, window_seconds: int) -> bool: ...


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._data: dict[str, list] = {}  # key -> [count, window_start_epoch]

    def allow(self, key, *, limit, window_seconds):
        now = time.time()
        entry = self._data.get(key)
        if entry is None or now - entry[1] >= window_seconds:
            self._data[key] = [1, now]
            return True
        entry[0] += 1
        return entry[0] <= limit


class RedisRateLimiter:
    def __init__(self, redis_url: str, prefix: str = "rl:") -> None:
        import redis

        self._redis = redis.from_url(redis_url, socket_connect_timeout=2)
        self._prefix = prefix

    def allow(self, key, *, limit, window_seconds):
        k = f"{self._prefix}{key}"
        count = self._redis.incr(k)
        if count == 1:
            self._redis.expire(k, window_seconds)  # TTL only on first hit (fixed window)
        return count <= limit
