from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.db.seed import PERMISSIONS
from app.db.session import get_session
from app.dependencies import get_lockout_store, get_refresh_store
from app.main import create_app
from app.models.auth import Organization, OrganizationMembership, Role
from app.models.enums import ImportFormat, OrgKind, RoleName
from app.models.etl import ChapterDomainMapping, EtlDataset
from app.models.taxonomy import ExamBlueprint, ExamDomain
from app.services.auth import InMemoryLockoutStore, register_user

FIXTURE = Path(__file__).parent / "fixtures" / "mini"


@pytest.fixture
def client_and_store(db_session, session_with_roles):
    """TestClient whose /api/etl routes share the test's own session/connection.

    session_with_roles seeds roles + permissions into db_session so auth helpers
    can mint tokens and promote users. Returns (client, refresh_store).
    """
    app = create_app()
    refresh_store = InMemoryRefreshTokenStore()
    lockout = InMemoryLockoutStore()

    def _session():
        yield db_session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_refresh_store] = lambda: refresh_store
    app.dependency_overrides[get_lockout_store] = lambda: lockout
    return TestClient(app), refresh_store


def _seed(session):
    org = Organization(slug="api-org", name="API", kind=OrgKind.personal)
    session.add(org); session.flush()
    bp = ExamBlueprint(version_label="api", effective_date=date(2024, 4, 15),
                       min_items=1, max_items=2, duration_minutes=60,
                       passing_score=700, max_score=1000, is_current=True)
    session.add(bp); session.flush()
    for n in (1, 2):
        session.add(ExamDomain(blueprint_id=bp.id, number=n, name=f"D{n}", weight_pct=10))
    session.flush()
    d1 = session.execute(select(ExamDomain).filter_by(number=1)).scalar_one()
    d2 = session.execute(select(ExamDomain).filter_by(number=2)).scalar_one()
    session.add(ChapterDomainMapping(dataset_slug="mini", chapter_number=1, domain_id=d1.id, chapter_title="Chapter One"))
    session.add(ChapterDomainMapping(dataset_slug="mini", chapter_number=2, domain_id=d2.id, chapter_title="Chapter Two"))
    session.add(EtlDataset(organization_id=org.id, slug="mini", name="Mini", source_path=str(FIXTURE),
                           format=ImportFormat.json, total_questions=3, languages=["en", "zh"]))
    session.flush()
    return org.id


def _admin_headers(db_session, store, email="etladmin@example.com"):
    """Mint an Authorization header for a system_admin user (all perms)."""
    user, _ = register_user(db_session, email=email, password="pw123456",
                            display_name="Etl", refresh_store=store)
    db_session.flush()
    sa = db_session.query(Role).filter_by(name=RoleName.system_admin).first()
    if sa is None:
        sa = Role(name=RoleName.system_admin, description="sysadmin")
        db_session.add(sa); db_session.flush()
    m = db_session.query(OrganizationMembership).filter_by(user_id=user.id).one()
    m.role_id = sa.id
    db_session.flush()
    token = create_access_token(
        user_id=user.id, org_id=user.default_organization_id,
        roles=["system_admin"], perms=[c for c, _ in PERMISSIONS],
    )
    return {"Authorization": f"Bearer {token}"}


def test_list_datasets(client_and_store, db_session):
    c, store = client_and_store
    _seed(db_session)
    headers = _admin_headers(db_session, store)
    resp = c.get("/api/etl/datasets", headers=headers)
    assert resp.status_code == 200
    slugs = [d["slug"] for d in resp.json()]
    assert "mini" in slugs


def test_get_dataset_404(client_and_store, db_session):
    c, store = client_and_store
    _seed(db_session)
    headers = _admin_headers(db_session, store)
    resp = c.get("/api/etl/datasets/does-not-exist", headers=headers)
    assert resp.status_code == 404


def test_list_mappings(client_and_store, db_session):
    c, store = client_and_store
    _seed(db_session)
    headers = _admin_headers(db_session, store)
    resp = c.get("/api/etl/mappings?dataset_slug=mini", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_create_and_rollback_run(client_and_store, db_session):
    c, store = client_and_store
    _seed(db_session)
    headers = _admin_headers(db_session, store)
    # preview
    resp = c.post("/api/etl/runs", json={"dataset_slug": "mini"}, headers=headers)
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["run_id"]
    assert resp.json()["phase"] == "preview"
    # one bilingual CleanedQuestion per external_id (3 raws -> 3 would-create)
    assert resp.json()["preview_summary"]["would_create"] == 3
    # rollback (writes nothing)
    rb = c.post(f"/api/etl/runs/{run_id}/rollback", headers=headers)
    assert rb.status_code == 200
    assert rb.json()["phase"] == "rolled_back"
    from app.models.question import Question
    assert db_session.execute(select(Question)).scalars().all() == []


def test_commit_run_writes_rows(client_and_store, db_session):
    c, store = client_and_store
    _seed(db_session)
    headers = _admin_headers(db_session, store)
    resp = c.post("/api/etl/runs", json={"dataset_slug": "mini"}, headers=headers)
    run_id = resp.json()["run_id"]
    commit = c.post(f"/api/etl/runs/{run_id}/commit", headers=headers)
    assert commit.status_code == 200, commit.text
    assert commit.json()["phase"] == "committed"
    from app.models.question import Question
    from sqlalchemy import func
    # one Question per external_id (3), not per (external_id, language)
    assert db_session.execute(select(func.count(Question.id))).scalar() == 3


def test_datasets_unauthenticated_401(client_and_store, db_session):
    c, _ = client_and_store
    _seed(db_session)
    assert c.get("/api/etl/datasets").status_code == 401


def test_runs_forbidden_without_perm(client_and_store, db_session):
    c, store = client_and_store
    _seed(db_session)
    # learner with no question:import perm
    user, _ = register_user(db_session, email="nop@e.com", password="pw123456",
                            display_name="N", refresh_store=store)
    db_session.flush()
    token = create_access_token(user_id=user.id, org_id=user.default_organization_id,
                                roles=["individual_learner"], perms=["question:read"])
    resp = c.post("/api/etl/runs", json={"dataset_slug": "mini"},
                  headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
