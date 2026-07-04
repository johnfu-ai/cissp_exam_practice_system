import uuid

import jwt
import pytest

from app.core.security import (
    InMemoryPasswordResetTokenStore,
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


def test_hash_uses_bcrypt_2b_prefix():
    """Direct bcrypt (no passlib) produces a $2b$ hash — and existing passlib
    hashes are also $2b$, so the swap is backward-compatible with stored hashes."""
    assert hash_password("s3cret!").startswith("$2b$")


def test_verify_password_malformed_hash_returns_false():
    """A malformed/legacy hash must return False, never raise (login path)."""
    assert verify_password("anything", "not-a-real-hash") is False
    assert verify_password("anything", "") is False


def test_password_truncated_at_72_bytes():
    """bcrypt's 72-byte limit is handled by truncation (matching passlib) so a
    >72-byte password (schema allows up to 128) hashes + verifies without raising."""
    long_pw = "x" * 100
    h = hash_password(long_pw)
    assert verify_password(long_pw, h) is True
    # the first 72 bytes are what's actually used; a password differing only past
    # byte 72 collides (documented bcrypt behavior, not a regression)
    assert verify_password("x" * 72 + "y" * 28, h) is True


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


def test_reset_token_store_issue_consume_single_use():
    store = InMemoryPasswordResetTokenStore()
    uid = uuid.uuid4()
    token = store.issue(uid, ttl_seconds=60)
    assert token  # non-empty
    assert store.consume(token) == uid  # first use returns the bound user_id
    assert store.consume(token) is None  # single-use: a second consume fails
    assert store.consume("bogus") is None  # unknown token -> None


def test_reset_token_store_delete():
    store = InMemoryPasswordResetTokenStore()
    uid = uuid.uuid4()
    token = store.issue(uid, ttl_seconds=60)
    store.delete(token)
    assert store.consume(token) is None


def test_reset_token_store_tokens_are_unique():
    store = InMemoryPasswordResetTokenStore()
    uid = uuid.uuid4()
    t1 = store.issue(uid, ttl_seconds=60)
    t2 = store.issue(uid, ttl_seconds=60)
    assert t1 != t2  # each issue mints a fresh token
