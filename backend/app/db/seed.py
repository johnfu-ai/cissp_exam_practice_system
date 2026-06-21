"""Idempotent system-reference seed.

Run via `python -m app.db.seed` or call run_seed(session). Re-running upserts;
guarded by SchemaMeta.seed_version.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin import SchemaMeta
from app.models.auth import Organization, Permission, Role, RolePermission
from app.models.enums import OrgKind, RoleName
from app.models.taxonomy import ExamBlueprint, ExamDomain

SEED_VERSION = "1"

# PRD §2 — CISSP 2024-04-15 blueprint weights.
DOMAINS = [
    (1, "Security and Risk Management", 16),
    (2, "Asset Security", 10),
    (3, "Security Architecture and Engineering", 13),
    (4, "Communication and Network Security", 13),
    (5, "Identity and Access Management (IAM)", 13),
    (6, "Security Assessment and Testing", 12),
    (7, "Security Operations", 13),
    (8, "Software Development Security", 10),
]

# Base permission codes. Enforcing endpoints arrive in sub-projects B-H.
PERMISSIONS = [
    ("question:read", "Read questions"),
    ("question:write", "Create/edit questions"),
    ("question:publish", "Publish/archive questions"),
    ("question:import", "Import question batches"),
    ("practice:read", "Start/view practice sessions"),
    ("exam:read", "Start/view exams"),
    ("admin:manage_users", "Manage users and roles"),
    ("admin:manage_taxonomy", "Manage exam config and taxonomy"),
    ("admin:view_audit", "View audit logs"),
]

# Role -> permission codes. system_admin gets everything.
ROLE_PERMISSIONS = {
    RoleName.individual_learner: ["question:read", "practice:read", "exam:read"],
    RoleName.instructor: ["question:read", "practice:read", "exam:read", "admin:manage_users"],
    RoleName.content_editor: ["question:read", "question:write", "question:publish", "question:import"],
    RoleName.org_admin: [
        "question:read", "question:write", "question:publish", "question:import",
        "practice:read", "exam:read", "admin:manage_users", "admin:view_audit",
    ],
    RoleName.system_admin: [code for code, _ in PERMISSIONS],
}


def _get_or_create(session, model, defaults=None, **filters):
    obj = session.execute(select(model).filter_by(**filters)).scalar_one_or_none()
    if obj is None:
        params = {**filters}
        if defaults:
            params.update(defaults)
        obj = model(**params)
        session.add(obj)
        session.flush()
    return obj


def run_seed(session: Session) -> dict:
    counts = {"organizations": 0, "blueprints": 0, "domains": 0, "roles": 0, "permissions": 0}

    # Organization: the built-in personal org.
    _get_or_create(
        session,
        Organization,
        slug="personal",
        defaults={"name": "Personal", "kind": OrgKind.personal},
    )
    counts["organizations"] = 1

    # Exam blueprint.
    bp = _get_or_create(
        session,
        ExamBlueprint,
        version_label="2024-04-15",
        defaults={
            "effective_date": date(2024, 4, 15),
            "min_items": 100,
            "max_items": 150,
            "duration_minutes": 180,
            "passing_score": 700,
            "max_score": 1000,
            "is_current": True,
        },
    )
    counts["blueprints"] = 1

    # Domains.
    for number, name, weight in DOMAINS:
        _get_or_create(
            session,
            ExamDomain,
            blueprint_id=bp.id,
            number=number,
            defaults={"name": name, "weight_pct": weight},
        )
    counts["domains"] = len(DOMAINS)

    # Permissions.
    perm_by_code = {}
    for code, desc in PERMISSIONS:
        perm_by_code[code] = _get_or_create(
            session, Permission, code=code, defaults={"description": desc}
        )
    counts["permissions"] = len(PERMISSIONS)

    # Roles + role_permissions.
    role_by_name = {}
    for role_name in RoleName:
        role_by_name[role_name] = _get_or_create(
            session, Role, name=role_name, defaults={"description": role_name.value}
        )
    counts["roles"] = len(RoleName)

    for role_name, codes in ROLE_PERMISSIONS.items():
        role = role_by_name[role_name]
        for code in codes:
            perm = perm_by_code[code]
            existing = session.execute(
                select(RolePermission).filter_by(role_id=role.id, permission_id=perm.id)
            ).scalar_one_or_none()
            if existing is None:
                session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    session.flush()

    # Seed version marker.
    _get_or_create(session, SchemaMeta, key="seed_version", defaults={"value": SEED_VERSION})

    return counts


def main() -> None:
    from app.db.session import get_sessionmaker

    session = get_sessionmaker()()
    try:
        result = run_seed(session)
        session.commit()
        print(f"Seed complete: {result}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
