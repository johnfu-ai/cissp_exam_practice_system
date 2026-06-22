from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.etl import router as etl_router
from app.db.session import get_session
from app.main import create_app
from app.models.auth import Organization
from app.models.enums import ImportFormat, OrgKind
from app.models.etl import ChapterDomainMapping, EtlDataset
from app.models.taxonomy import ExamBlueprint, ExamDomain

FIXTURE = Path(__file__).parent / "fixtures" / "mini"


@pytest.fixture
def client(db_session):
    """A TestClient whose /api/etl routes share the test's own session/connection.

    The db_session fixture holds an uncommitted savepoint on its connection; if
    the app opened its own session it would not see that data. Overriding
    get_session to return db_session makes the app read/write through the same
    connection the test seeds.
    """
    app = create_app()

    def _override_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    return TestClient(app)


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


def test_list_datasets(client, db_session):
    _seed(db_session)
    resp = client.get("/api/etl/datasets")
    assert resp.status_code == 200
    slugs = [d["slug"] for d in resp.json()]
    assert "mini" in slugs


def test_get_dataset_404(client, db_session):
    _seed(db_session)
    resp = client.get("/api/etl/datasets/does-not-exist")
    assert resp.status_code == 404


def test_list_mappings(client, db_session):
    _seed(db_session)
    resp = client.get("/api/etl/mappings?dataset_slug=mini")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_create_and_rollback_run(client, db_session):
    org_id = _seed(db_session)
    # preview
    resp = client.post("/api/etl/runs", json={"dataset_slug": "mini"})
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["run_id"]
    assert resp.json()["phase"] == "preview"
    assert resp.json()["preview_summary"]["would_create"] == 6
    # rollback (writes nothing)
    rb = client.post(f"/api/etl/runs/{run_id}/rollback")
    assert rb.status_code == 200
    assert rb.json()["phase"] == "rolled_back"
    from app.models.question import Question
    assert db_session.execute(select(Question)).scalars().all() == []


def test_commit_run_writes_rows(client, db_session):
    _seed(db_session)
    resp = client.post("/api/etl/runs", json={"dataset_slug": "mini"})
    run_id = resp.json()["run_id"]
    commit = client.post(f"/api/etl/runs/{run_id}/commit")
    assert commit.status_code == 200, commit.text
    assert commit.json()["phase"] == "committed"
    from app.models.question import Question
    from sqlalchemy import func
    assert db_session.execute(select(func.count(Question.id))).scalar() == 6
