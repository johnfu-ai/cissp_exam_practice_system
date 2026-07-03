import pytest

from app.core.security import (
    InMemoryPasswordResetTokenStore,
    InMemoryRefreshTokenStore,
    verify_password,
)
from app.models.auth import Organization, OrganizationMembership, Role
from app.models.enums import OrgKind, RoleName
from app.services.auth import (
    AuthError,
    InMemoryLockoutStore,
    authenticate,
    change_password,
    confirm_password_reset,
    load_user_perms,
    logout,
    refresh_tokens,
    register_user,
    request_password_reset,
)


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
    org = session.get(Organization, user.default_organization_id)
    assert org.kind == OrgKind.personal
    m = session.query(OrganizationMembership).filter_by(user_id=user.id).one()
    role = session.get(Role, m.role_id)
    assert role.name == RoleName.individual_learner
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
    assert set(perms) >= {"question:read", "practice:read", "exam:read"}


# ---- P0 #1: secure password change + reset ----

def test_change_password_rejects_wrong_current(session_with_roles):
    session = session_with_roles
    store = InMemoryRefreshTokenStore()
    user, _ = register_user(session, email="cp@example.com", password="pw123456",
                            display_name="CP", refresh_store=store)
    session.flush()
    with pytest.raises(AuthError) as exc:
        change_password(session, user=user, current_password="wrong", new_password="newpw123")
    assert exc.value.status_code == 401
    # original password still works
    assert verify_password("pw123456", user.password_hash)


def test_change_password_updates_hash_and_audits(session_with_roles):
    session = session_with_roles
    store = InMemoryRefreshTokenStore()
    user, _ = register_user(session, email="cp2@example.com", password="pw123456",
                            display_name="CP2", refresh_store=store)
    session.flush()
    change_password(session, user=user, current_password="pw123456", new_password="newpw123")
    session.flush()
    assert verify_password("newpw123", user.password_hash)
    assert not verify_password("pw123456", user.password_hash)
    # audit row written as password_change
    from app.models.admin import AuditLog
    rows = session.query(AuditLog).filter_by(
        action="password_change", entity_id=str(user.id)).all()
    assert len(rows) == 1


def test_request_reset_issues_token_for_known_email(session_with_roles):
    session = session_with_roles
    store = InMemoryRefreshTokenStore()
    rst = InMemoryPasswordResetTokenStore()
    register_user(session, email="rr@example.com", password="pw123456",
                  display_name="RR", refresh_store=store)
    session.flush()
    token = request_password_reset(
        session, email="rr@example.com", reset_store=rst,
        lockout_store=InMemoryLockoutStore(threshold=5))
    assert token is not None
    assert rst.consume(token) is not None


def test_request_reset_unknown_email_returns_none_no_raise(session_with_roles):
    session = session_with_roles
    rst = InMemoryPasswordResetTokenStore()
    token = request_password_reset(
        session, email="nope@example.com", reset_store=rst,
        lockout_store=InMemoryLockoutStore(threshold=5))
    assert token is None  # no leak, no raise


def test_request_reset_locks_after_threshold_misses(session_with_roles):
    session = session_with_roles
    rst = InMemoryPasswordResetTokenStore()
    lockout = InMemoryLockoutStore(threshold=3)
    for _ in range(3):
        request_password_reset(session, email="nope@example.com",
                               reset_store=rst, lockout_store=lockout)
    with pytest.raises(AuthError) as exc:
        request_password_reset(session, email="nope@example.com",
                               reset_store=rst, lockout_store=lockout)
    assert exc.value.status_code == 429


def test_confirm_reset_consumes_token_and_sets_password(session_with_roles):
    session = session_with_roles
    store = InMemoryRefreshTokenStore()
    rst = InMemoryPasswordResetTokenStore()
    user, _ = register_user(session, email="cr@example.com", password="pw123456",
                            display_name="CR", refresh_store=store)
    session.flush()
    token = request_password_reset(
        session, email="cr@example.com", reset_store=rst,
        lockout_store=InMemoryLockoutStore(threshold=5))
    confirmed = confirm_password_reset(
        session, token=token, new_password="newpw123", reset_store=rst)
    session.flush()
    assert confirmed.id == user.id
    assert verify_password("newpw123", user.password_hash)
    # single-use: a second confirm with the same token fails
    with pytest.raises(AuthError):
        confirm_password_reset(session, token=token, new_password="another123",
                               reset_store=rst)


def test_confirm_reset_bogus_token_raises(session_with_roles):
    session = session_with_roles
    rst = InMemoryPasswordResetTokenStore()
    with pytest.raises(AuthError) as exc:
        confirm_password_reset(session, token="bogus", new_password="newpw123",
                               reset_store=rst)
    assert exc.value.status_code == 401
