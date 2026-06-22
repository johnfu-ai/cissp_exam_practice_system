"""Admin backoffice service (FR-ADMIN-03..07).

All queries are org-scoped for org_admin (current.org_id) and global for
system_admin (None scope). Out-of-scope targets raise NotFound (not 403) to
avoid leaking existence. Mutations write AuditLog via log_audit (flush only;
caller commits).

This module is built up across tasks 4-8 of sub-project H2. Task 4 adds the
exception hierarchy, the org-scoping helper, and the user-management +
class-management functions (FR-ADMIN-03). Later tasks append CAT-params,
quality, audit, and reports functions to this same file.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.queries import not_deleted
from app.dependencies import CurrentUser
from app.models.admin import CatParamsVersion
from app.models.auth import (
    Class,
    ClassMembership,
    OrganizationMembership,
    Role,
    RoleName,
    User,
)
from app.models.enums import AuditAction, UserStatus
from app.schemas.admin import (
    CatParamsIn,
    CatParamsVersionOut,
    ClassIn,
    ClassMemberOut,
    ClassOut,
    UserOut,
)
from app.services.audit import log_audit


class AdminError(Exception):
    """Base for all admin-service errors. The router (Task 9) catches this one
    base and maps subclasses to HTTP statuses (422/404/409)."""


class ValidationError(AdminError):
    pass


class NotFound(AdminError):
    pass


class ConflictError(AdminError):
    pass


_SYSTEM_ADMIN = RoleName.system_admin.value


def _admin_org_scope(current: CurrentUser) -> uuid.UUID | None:
    """None for system_admin (global); org_id for everyone else."""
    if _SYSTEM_ADMIN in current.roles:
        return None
    return current.org_id


def _user_out(session: Session, user: User, org_id: uuid.UUID) -> UserOut:
    role_names = [
        r.value
        for r in session.execute(
            select(Role.name)
            .join(OrganizationMembership, OrganizationMembership.role_id == Role.id)
            .where(OrganizationMembership.user_id == user.id,
                   OrganizationMembership.organization_id == org_id)
        ).scalars()
    ]
    return UserOut(
        id=user.id, email=user.email, display_name=user.display_name,
        status=user.status.value, default_organization_id=user.default_organization_id,
        roles=role_names,
    )


def _resolve_scope_org(current: CurrentUser, user: User) -> uuid.UUID:
    """Org to use for role listing: admin scope (org_admin) or user's default org (system_admin)."""
    scope = _admin_org_scope(current)
    return scope if scope is not None else (user.default_organization_id or current.org_id)


# ---- FR-ADMIN-03: users ----

def list_users(session, *, current, search=None, limit=50, offset=0):
    scope = _admin_org_scope(current)
    filters = []
    if scope is not None:
        filters.append(OrganizationMembership.organization_id == scope)
    if search:
        filters.append(or_(User.email.ilike(f"%{search}%"),
                           User.display_name.ilike(f"%{search}%")))
    # count DISTINCT users so a user with N roles in the same org counts once,
    # matching the deduped `rows` query below (which uses .scalars().unique()).
    count_q = (select(func.count(func.distinct(User.id)))
               .select_from(User)
               .join(OrganizationMembership,
                     OrganizationMembership.user_id == User.id))
    for f in filters:
        count_q = count_q.where(f)
    total = session.execute(count_q).scalar_one()
    rows_q = select(User).join(OrganizationMembership,
                               OrganizationMembership.user_id == User.id)
    for f in filters:
        rows_q = rows_q.where(f)
    rows = session.execute(
        rows_q.order_by(User.email).limit(limit).offset(offset)
    ).scalars().unique().all()
    out = [_user_out(session, u, _resolve_scope_org(current, u)) for u in rows]
    return out, total


def get_user(session, *, current, user_id):
    user = session.get(User, user_id)
    if user is None:
        raise NotFound("user not found")
    scope = _admin_org_scope(current)
    if scope is not None:
        # Existence check only (a user may have multiple roles in the same org,
        # i.e. multiple OrganizationMembership rows). Use .first(), not
        # .scalar_one_or_none(), which raises MultipleResultsFound on multi-role
        # users (set_user_roles itself creates such memberships).
        in_org = session.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.organization_id == scope,
            )
        ).first()
        if in_org is None:
            raise NotFound("user not found")
    return _user_out(session, user, _resolve_scope_org(current, user))


def set_user_status(session, *, current, user_id, status: UserStatus):
    user = session.get(User, user_id)
    if user is None:
        raise NotFound("user not found")
    get_user(session, current=current, user_id=user_id)  # scope check -> NotFound
    user.status = status
    session.flush()
    log_audit(session, action=AuditAction.permission_change, actor_id=current.user.id,
              organization_id=current.org_id, entity_type="user", entity_id=str(user_id),
              details={"status": status.value})
    return _user_out(session, user, _resolve_scope_org(current, user))


def set_user_roles(session, *, current, user_id, role_names: list[RoleName]):
    user = session.get(User, user_id)
    if user is None:
        raise NotFound("user not found")
    org_id = _resolve_scope_org(current, user)
    # scope check
    if _admin_org_scope(current) is not None:
        get_user(session, current=current, user_id=user_id)
    role_ids = []
    for name in role_names:
        r = session.execute(select(Role).where(Role.name == name)).scalar_one_or_none()
        if r is None:
            raise ValidationError(f"unknown role {name}")
        role_ids.append(r.id)
    # replace memberships in this org only (select-then-delete, project convention)
    existing = session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == org_id,
        )
    ).scalars().all()
    for m in existing:
        session.delete(m)
    for rid in role_ids:
        session.add(OrganizationMembership(user_id=user_id, organization_id=org_id, role_id=rid))
    session.flush()
    log_audit(session, action=AuditAction.permission_change, actor_id=current.user.id,
              organization_id=org_id, entity_type="user", entity_id=str(user_id),
              details={"roles": [n.value for n in role_names]})
    return _user_out(session, user, org_id)


# ---- FR-ADMIN-03: classes ----

def _class_out(session, cls: Class) -> ClassOut:
    count = session.execute(
        select(func.count()).select_from(
            select(ClassMembership).where(ClassMembership.class_id == cls.id).subquery()
        )
    ).scalar_one()
    return ClassOut(id=cls.id, name=cls.name, description=cls.description,
                    instructor_id=cls.instructor_id, organization_id=cls.organization_id,
                    member_count=count)


def _scoped_class(session, current, class_id) -> Class:
    q = select(Class).where(Class.id == class_id, not_deleted(Class))
    scope = _admin_org_scope(current)
    if scope is not None:
        q = q.where(Class.organization_id == scope)
    cls = session.execute(q).scalar_one_or_none()
    if cls is None:
        raise NotFound("class not found")
    return cls


def list_classes(session, *, current, limit=50, offset=0):
    q = select(Class).where(not_deleted(Class))
    scope = _admin_org_scope(current)
    if scope is not None:
        q = q.where(Class.organization_id == scope)
    total = session.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = session.execute(q.order_by(Class.name).limit(limit).offset(offset)).scalars().all()
    return [_class_out(session, c) for c in rows], total


def create_class(session, *, current, payload: ClassIn) -> ClassOut:
    scope = _admin_org_scope(current) or current.org_id
    cls = Class(organization_id=scope, name=payload.name,
                description=payload.description, instructor_id=payload.instructor_id)
    session.add(cls); session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=current.user.id, organization_id=scope,
              entity_type="class", entity_id=str(cls.id), details={"name": payload.name})
    return _class_out(session, cls)


def get_class(session, *, current, class_id) -> ClassOut:
    return _class_out(session, _scoped_class(session, current, class_id))


def update_class(session, *, current, class_id, payload: ClassIn) -> ClassOut:
    cls = _scoped_class(session, current, class_id)
    cls.name = payload.name
    cls.description = payload.description
    cls.instructor_id = payload.instructor_id
    session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=current.user.id,
              organization_id=cls.organization_id, entity_type="class",
              entity_id=str(cls.id), details={"name": payload.name})
    return _class_out(session, cls)


def delete_class(session, *, current, class_id) -> None:
    cls = _scoped_class(session, current, class_id)
    cls.deleted_at = datetime.now(timezone.utc)
    session.flush()
    log_audit(session, action=AuditAction.archive, actor_id=current.user.id,
              organization_id=cls.organization_id, entity_type="class",
              entity_id=str(cls.id), details={"name": cls.name})


def list_class_members(session, *, current, class_id):
    cls = _scoped_class(session, current, class_id)
    rows = session.execute(
        select(User)
        .join(ClassMembership, ClassMembership.user_id == User.id)
        .where(ClassMembership.class_id == cls.id)
        .order_by(User.email)
    ).scalars().all()
    return [ClassMemberOut(user_id=u.id, email=u.email, display_name=u.display_name)
            for u in rows]


def add_class_member(session, *, current, class_id, user_id) -> None:
    cls = _scoped_class(session, current, class_id)
    # user must be in the class's org
    scope = _admin_org_scope(current)
    org_filter = scope if scope is not None else cls.organization_id
    # Existence check only; a user with multiple roles in the org has multiple
    # matching rows, so use .first() (not .scalar_one_or_none()).
    m = session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == org_filter,
        )
    ).first()
    if m is None:
        raise NotFound("user not found")
    existing = session.execute(
        select(ClassMembership).where(ClassMembership.class_id == cls.id,
                                      ClassMembership.user_id == user_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("already a member")
    session.add(ClassMembership(class_id=cls.id, user_id=user_id)); session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=current.user.id,
              organization_id=cls.organization_id, entity_type="class_member",
              entity_id=str(cls.id), details={"user_id": str(user_id)})


def remove_class_member(session, *, current, class_id, user_id) -> None:
    cls = _scoped_class(session, current, class_id)
    m = session.execute(
        select(ClassMembership).where(ClassMembership.class_id == cls.id,
                                      ClassMembership.user_id == user_id)
    ).scalar_one_or_none()
    if m is None:
        raise NotFound("membership not found")
    session.delete(m); session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=current.user.id,
              organization_id=cls.organization_id, entity_type="class_member",
              entity_id=str(cls.id), details={"removed_user_id": str(user_id)})


# ---- FR-ADMIN-04: CAT params ----
# CatParamsVersion is GLOBAL (organization_id=None on the audit row). Only one
# version may have is_current=True at a time; _unset_current clears the prior
# current before a new one is set. Mutations audit as config_change.

def _cat_out(v: CatParamsVersion) -> CatParamsVersionOut:
    return CatParamsVersionOut(id=v.id, version_label=v.version_label,
                               effective_date=v.effective_date, is_current=v.is_current,
                               params=v.params)


def list_cat_params(session) -> list[CatParamsVersionOut]:
    rows = session.execute(
        select(CatParamsVersion).order_by(CatParamsVersion.effective_date.desc())
    ).scalars().all()
    return [_cat_out(v) for v in rows]


def _unset_current(session) -> None:
    # ORM-level update (not a Core bulk UPDATE) so identity-mapped objects stay
    # consistent with the DB — a Core update().values() would leave in-memory
    # rows stale, breaking the "v1.is_current is False" check right after v2 is
    # created with set_current=True.
    rows = session.execute(
        select(CatParamsVersion).where(CatParamsVersion.is_current.is_(True))
    ).scalars().all()
    for v in rows:
        v.is_current = False


def create_cat_params(session, *, current, payload: CatParamsIn) -> CatParamsVersionOut:
    dup = session.execute(
        select(CatParamsVersion).where(CatParamsVersion.version_label == payload.version_label)
    ).scalar_one_or_none()
    if dup is not None:
        raise ConflictError("version_label already exists")
    if payload.set_current:
        _unset_current(session)
    v = CatParamsVersion(version_label=payload.version_label,
                        effective_date=payload.effective_date,
                        is_current=payload.set_current,
                        params=payload.params.model_dump())
    session.add(v); session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=current.user.id,
              organization_id=None, entity_type="cat_params",
              entity_id=str(v.id), details={"version_label": v.version_label,
                                            "set_current": v.is_current})
    return _cat_out(v)


def set_current_cat_params(session, *, current, version_id) -> CatParamsVersionOut:
    v = session.get(CatParamsVersion, version_id)
    if v is None:
        raise NotFound("cat params version not found")
    _unset_current(session)
    v.is_current = True
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=current.user.id,
              organization_id=None, entity_type="cat_params",
              entity_id=str(v.id), details={"set_current": True})
    return _cat_out(v)


def get_current_cat_params(session) -> CatParamsVersion | None:
    return session.execute(
        select(CatParamsVersion).where(CatParamsVersion.is_current.is_(True))
    ).scalar_one_or_none()
