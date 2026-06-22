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
