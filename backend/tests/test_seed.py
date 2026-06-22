from sqlalchemy import func, select

from app.db.seed import run_seed
from app.models.admin import SchemaMeta
from app.models.auth import Organization, OrganizationMembership, Permission, Role, RolePermission, User
from app.models.enums import RoleName
from app.models.etl import ChapterDomainMapping, EtlDataset
from app.models.taxonomy import ExamBlueprint, ExamDomain


def test_seed_creates_expected_reference_data(db_session):
    result = run_seed(db_session)
    assert result["organizations"] == 1
    assert result["blueprints"] == 1
    assert result["domains"] == 8
    assert result["roles"] == 5

    org = db_session.execute(select(Organization).filter_by(slug="personal")).scalar_one()
    assert org.kind.value == "personal"

    bp = db_session.execute(
        select(ExamBlueprint).filter_by(version_label="2024-04-15")
    ).scalar_one()
    assert bp.is_current is True
    assert bp.min_items == 100 and bp.max_items == 150
    assert bp.duration_minutes == 180
    assert bp.passing_score == 700 and bp.max_score == 1000

    total_weight = db_session.execute(
        select(func.coalesce(func.sum(ExamDomain.weight_pct), 0)).where(
            ExamDomain.blueprint_id == bp.id
        )
    ).scalar_one()
    assert total_weight == 100

    role_count = db_session.execute(select(func.count()).select_from(Role)).scalar_one()
    assert role_count == 5


def test_seed_is_idempotent(db_session):
    run_seed(db_session)
    counts_1_perm = db_session.execute(
        select(func.count()).select_from(Permission)
    ).scalar_one()
    counts_1_rp = db_session.execute(
        select(func.count()).select_from(RolePermission)
    ).scalar_one()

    run_seed(db_session)  # second run

    counts_2_perm = db_session.execute(
        select(func.count()).select_from(Permission)
    ).scalar_one()
    counts_2_rp = db_session.execute(
        select(func.count()).select_from(RolePermission)
    ).scalar_one()

    assert counts_1_perm == counts_2_perm
    assert counts_1_rp == counts_2_rp

    sv = db_session.execute(select(SchemaMeta).filter_by(key="seed_version")).scalar_one()
    assert sv.value == "3"


def test_system_admin_has_all_permissions(db_session):
    run_seed(db_session)
    admin_role = db_session.execute(
        select(Role).filter_by(name=RoleName.system_admin)
    ).scalar_one()
    rp_count = db_session.execute(
        select(func.count()).select_from(RolePermission).where(
            RolePermission.role_id == admin_role.id
        )
    ).scalar_one()
    perm_total = db_session.execute(
        select(func.count()).select_from(Permission)
    ).scalar_one()
    assert rp_count == perm_total


def test_seed_creates_osg10_dataset_and_mappings(db_session):
    run_seed(db_session)
    ds = db_session.execute(select(EtlDataset).filter_by(slug="osg10")).scalar_one()
    assert ds.total_questions == 420
    assert ds.languages == ["en", "zh"]
    mappings = db_session.execute(
        select(ChapterDomainMapping).filter_by(dataset_slug="osg10")
    ).scalars().all()
    assert len(mappings) == 21


def test_seed_osg10_is_idempotent(db_session):
    run_seed(db_session)
    run_seed(db_session)
    count = len(
        db_session.execute(
            select(ChapterDomainMapping).filter_by(dataset_slug="osg10")
        ).scalars().all()
    )
    assert count == 21


def test_seed_creates_bootstrap_admin(db_session):
    run_seed(db_session)
    admin = db_session.execute(select(User).filter_by(email="admin@example.com")).scalar_one()
    assert admin.password_hash
    m = db_session.execute(
        select(OrganizationMembership).filter_by(user_id=admin.id)
    ).scalar_one()
    role = db_session.get(Role, m.role_id)
    assert role.name == RoleName.system_admin
