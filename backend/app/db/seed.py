"""Idempotent system-reference seed.

Run via `python -m app.db.seed` or call run_seed(session). Re-running upserts;
guarded by SchemaMeta.seed_version.
"""

import secrets
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.admin import SchemaMeta
from app.models.auth import Organization, OrganizationMembership, Permission, Role, RolePermission, User
from app.models.enums import ImportFormat, OrgKind, RoleName, UserStatus
from app.models.etl import ChapterDomainMapping, EtlDataset
from app.models.taxonomy import ExamBlueprint, ExamDomain

SEED_VERSION = "4"

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
    ("admin:view_reports", "View operational reports"),
]

# Role -> permission codes. system_admin gets everything.
ROLE_PERMISSIONS = {
    RoleName.individual_learner: ["question:read", "practice:read", "exam:read"],
    RoleName.instructor: ["question:read", "practice:read", "exam:read", "admin:manage_users"],
    RoleName.content_editor: ["question:read", "question:write", "question:publish", "question:import"],
    RoleName.org_admin: [
        "question:read", "question:write", "question:publish", "question:import",
        "practice:read", "exam:read", "admin:manage_users", "admin:view_audit",
        "admin:view_reports",
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
    counts = {
        "organizations": 0,
        "blueprints": 0,
        "domains": 0,
        "roles": 0,
        "permissions": 0,
        "datasets": 0,
        "chapter_mappings": 0,
    }

    # Organization: the built-in personal org.
    personal_org = _get_or_create(
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

    # Bootstrap system_admin (so the system is usable after auth lock-down).
    admin_email = settings.seed_admin_email.lower()
    admin = session.execute(select(User).filter_by(email=admin_email)).scalar_one_or_none()
    if admin is None:
        pw = settings.seed_admin_password or secrets.token_urlsafe(16)
        admin = User(email=admin_email, password_hash=hash_password(pw),
                     display_name="System Admin", status=UserStatus.active,
                     default_organization_id=personal_org.id)
        session.add(admin); session.flush()
        if not settings.seed_admin_password:
            print(f"[seed] created admin {admin_email} with generated password: {pw}")
    elif settings.seed_admin_password:
        # An explicit seed password always wins — keeps dev logins (e.g. admin/admin)
        # working across restarts even when the admin already exists.
        new_hash = hash_password(settings.seed_admin_password)
        if admin.password_hash != new_hash:
            admin.password_hash = new_hash
            print(f"[seed] reset admin {admin_email} password to configured SEED_ADMIN_PASSWORD")
    # Ensure the admin holds the system_admin role in the personal org whether
    # the account was just created or already existed (idempotent).
    sa_role = role_by_name[RoleName.system_admin]
    existing = session.execute(
        select(OrganizationMembership).filter_by(
            user_id=admin.id, organization_id=personal_org.id, role_id=sa_role.id)
    ).scalar_one_or_none()
    if existing is None:
        session.add(OrganizationMembership(user_id=admin.id,
                                           organization_id=personal_org.id,
                                           role_id=sa_role.id))
    session.flush()

    # OSG v10 dataset + chapter->domain mapping (PRD §9.4, spec §9).
    osg10_path = "docs/questions/osg10"
    _get_or_create(
        session,
        EtlDataset,
        slug="osg10",
        defaults={
            "organization_id": personal_org.id,
            "name": "CISSP OSG v10",
            "source_path": osg10_path,
            "format": ImportFormat.json,
            "total_questions": 420,
            "languages": ["en", "zh"],
            "notes": "OSG 10th edition review questions, bilingual en/zh",
        },
    )
    domain_by_number = {
        d.number: d
        for d in session.execute(select(ExamDomain).filter_by(blueprint_id=bp.id)).scalars()
    }
    # (chapter_number, chapter_title, domain_number)
    osg10_chapters = [
        (1, "Security Governance Through Principles and Policies", 1),
        (2, "Personnel Security and Risk Management Concepts", 1),
        (3, "Business Continuity Planning", 1),
        (4, "Laws, Regulations, and Compliance", 1),
        (5, "Protecting Security of Assets", 2),
        (6, "Cryptography and Symmetric Key Algorithms", 3),
        (7, "PKI and Cryptographic Applications", 3),
        (8, "Principles of Security Models, Design, and Capabilities", 3),
        (9, "Security Vulnerabilities, Threats, and Countermeasures", 3),
        (10, "Physical Security Requirements", 3),
        (11, "Secure Network Architecture and Components", 4),
        (12, "Secure Communications and Network Attacks", 4),
        (13, "Managing Identity and Authentication", 5),
        (14, "Controlling and Monitoring Access", 5),
        (15, "Security Assessment and Testing", 6),
        (16, "Managing Security Operations", 7),
        (17, "Preventing and Responding to Incidents", 7),
        (18, "Disaster Recovery Planning", 7),
        (19, "Investigations and Ethics", 7),
        (20, "Software Development Security", 8),
        (21, "Malicious Code and Application Attacks", 8),
    ]
    for chapter_number, chapter_title, domain_number in osg10_chapters:
        _get_or_create(
            session,
            ChapterDomainMapping,
            dataset_slug="osg10",
            chapter_number=chapter_number,
            defaults={
                "domain_id": domain_by_number[domain_number].id,
                "chapter_title": chapter_title,
            },
        )
    session.flush()
    counts["datasets"] = 1
    counts["chapter_mappings"] = len(osg10_chapters)

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
