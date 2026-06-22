import pytest

from app.core.security import InMemoryRefreshTokenStore
from app.models.auth import Organization, OrganizationMembership, Role
from app.models.enums import OrgKind, RoleName
from app.services.auth import (
    AuthError,
    InMemoryLockoutStore,
    authenticate,
    load_user_perms,
    logout,
    refresh_tokens,
    register_user,
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
