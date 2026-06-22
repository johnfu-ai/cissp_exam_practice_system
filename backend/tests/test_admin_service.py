"""Service-layer tests for admin backoffice (sub-project H2, Task 4).

Covers user management + class management (FR-ADMIN-03). Seeds orgs/users on
the real ``cissp_test`` DB using module-level helpers matching
``test_exam_service.py`` / ``test_analytics.py`` conventions. Uses the
``session_with_roles`` fixture so every ``RoleName`` row + the permission
matrix already exist for ``OrganizationMembership`` and role lookups.
"""

import pytest

from app.db.seed import PERMISSIONS
from app.dependencies import CurrentUser
from app.models.auth import (
    Organization,
    OrganizationMembership,
    Role,
    RoleName,
    User,
)
from app.models.enums import OrgKind, OrgStatus, UserStatus
from app.schemas.admin import ClassIn
from app.services import admin as svc


def _org(db, slug):
    o = Organization(name=slug, slug=slug, kind=OrgKind.personal, status=OrgStatus.active)
    db.add(o); db.flush(); return o


def _user(db, email, org, status=UserStatus.active):
    u = User(email=email, status=status, default_organization_id=org.id)
    db.add(u); db.flush()
    db.add(OrganizationMembership(user_id=u.id, organization_id=org.id,
            role_id=db.query(Role).filter_by(name=RoleName.individual_learner).one().id))
    db.flush(); return u


def _current(db, org, role_name=RoleName.org_admin):
    role = db.query(Role).filter_by(name=role_name).one()
    return CurrentUser(user=_user(db, f"admin-{org.slug}@x.com", org),
                       org_id=org.id, roles=[role_name.value],
                       perms=[c for c, _ in PERMISSIONS])


def test_list_users_org_scoped(session_with_roles):
    db = session_with_roles
    o1, o2 = _org(db, "o1"), _org(db, "o2")
    _user(db, "a@x.com", o1); _user(db, "b@x.com", o2)
    cur = _current(db, o1)
    users, total = svc.list_users(db, current=cur, search=None, limit=50, offset=0)
    emails = {u.email for u in users}
    assert "a@x.com" in emails and "b@x.com" not in emails
    assert total >= 1


def test_org_admin_cannot_get_other_org_user(session_with_roles):
    db = session_with_roles
    o1, o2 = _org(db, "o1"), _org(db, "o2")
    target = _user(db, "x@x.com", o2)
    cur = _current(db, o1)
    with pytest.raises(svc.NotFound):
        svc.get_user(db, current=cur, user_id=target.id)


def test_set_user_status_audits(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    target = _user(db, "t@x.com", o1)
    cur = _current(db, o1)
    out = svc.set_user_status(db, current=cur, user_id=target.id, status=UserStatus.disabled)
    assert out.status == "disabled"
    db.flush()
    from app.models.admin import AuditLog
    logs = db.query(AuditLog).filter_by(entity_type="user", entity_id=str(target.id)).all()
    assert any(l.action.value == "permission_change" for l in logs)


def test_set_user_roles_scoped_to_org(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    target = _user(db, "t@x.com", o1)
    cur = _current(db, o1)
    out = svc.set_user_roles(db, current=cur, user_id=target.id,
                             role_names=[RoleName.instructor])
    assert out.roles == ["instructor"]
    # membership role updated
    m = db.query(OrganizationMembership).filter_by(user_id=target.id, organization_id=o1.id).one()
    assert m.role_id == db.query(Role).filter_by(name=RoleName.instructor).one().id


def test_class_crud_org_scoped(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _current(db, o1)
    c = svc.create_class(db, current=cur, payload=ClassIn(name="Sec A"))
    assert c.organization_id == o1.id
    got = svc.get_class(db, current=cur, class_id=c.id)
    assert got.name == "Sec A"
    upd = svc.update_class(db, current=cur, class_id=c.id,
                           payload=ClassIn(name="Sec B"))
    assert upd.name == "Sec B"
    svc.delete_class(db, current=cur, class_id=c.id)
    with pytest.raises(svc.NotFound):
        svc.get_class(db, current=cur, class_id=c.id)


def test_class_membership(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    target = _user(db, "m@x.com", o1)
    cur = _current(db, o1)
    c = svc.create_class(db, current=cur, payload=ClassIn(name="Sec A"))
    svc.add_class_member(db, current=cur, class_id=c.id, user_id=target.id)
    members = svc.list_class_members(db, current=cur, class_id=c.id)
    assert any(m.user_id == target.id for m in members)
    svc.remove_class_member(db, current=cur, class_id=c.id, user_id=target.id)
    assert not any(m.user_id == target.id for m in svc.list_class_members(db, current=cur, class_id=c.id))


def test_get_user_with_multiple_roles_in_same_org(session_with_roles):
    """Regression: a user with 2+ roles in the same org has multiple
    OrganizationMembership rows. get_user's org-scope existence check must use
    .first() (not .scalar_one_or_none()), which otherwise raises
    sqlalchemy.exc.MultipleResultsFound -> 500. set_user_roles itself creates
    such multi-role memberships, so this path is reachable in production."""
    db = session_with_roles
    o1 = _org(db, "o1")
    target = _user(db, "multi@x.com", o1)
    cur = _current(db, o1)
    # Give the target TWO roles in the same org -> two OrganizationMembership
    # rows for (user_id, organization_id) with different role_id.
    svc.set_user_roles(db, current=cur, user_id=target.id,
                       role_names=[RoleName.instructor, RoleName.content_editor])
    memberships = db.query(OrganizationMembership).filter_by(
        user_id=target.id, organization_id=o1.id).all()
    assert len(memberships) == 2  # sanity: the bug precondition holds

    # Before the fix this raised MultipleResultsFound (a 500 in the router).
    out = svc.get_user(db, current=cur, user_id=target.id)
    assert out.id == target.id
    assert set(out.roles) == {"instructor", "content_editor"}
