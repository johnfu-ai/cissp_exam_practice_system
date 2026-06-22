from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.db.seed import PERMISSIONS
from app.db.session import get_session
from app.dependencies import get_lockout_store, get_refresh_store
from app.main import create_app
from app.models.auth import Organization, OrganizationMembership, Role
from app.models.enums import OrgKind, RoleName
from app.models.question import Book, Chapter
from app.models.taxonomy import ExamBlueprint, ExamDomain, KnowledgePoint
from app.services.auth import InMemoryLockoutStore, register_user


@pytest.fixture
def client(db_session, session_with_roles):
    app = create_app()
    store = InMemoryRefreshTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: store
    app.dependency_overrides[get_lockout_store] = lambda: InMemoryLockoutStore()
    return TestClient(app), store, db_session


def _admin(db_session, store, email="tax@example.com"):
    """Register a system_admin user; return (headers, user)."""
    user, _ = register_user(db_session, email=email, password="pw123456",
                            display_name="Tax", refresh_store=store)
    db_session.flush()
    sa = db_session.query(Role).filter_by(name=RoleName.system_admin).first()
    m = db_session.query(OrganizationMembership).filter_by(user_id=user.id).one()
    m.role_id = sa.id
    db_session.flush()
    token = create_access_token(user_id=user.id, org_id=user.default_organization_id,
                                roles=["system_admin"], perms=[c for c, _ in PERMISSIONS])
    return {"Authorization": f"Bearer {token}"}, user


def _seed_globals(db_session):
    bp = ExamBlueprint(version_label="tax", effective_date=date(2024, 4, 15),
                       min_items=100, max_items=150, duration_minutes=180,
                       passing_score=700, max_score=1000, is_current=True)
    db_session.add(bp); db_session.flush()
    db_session.add_all([
        ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=16),
        ExamDomain(blueprint_id=bp.id, number=2, name="D2", weight_pct=10),
    ])
    db_session.add(KnowledgePoint(name="Risk"))
    db_session.flush()


def test_domains_global(client):
    c, store, db = client
    _seed_globals(db)
    h, _ = _admin(db, store)
    resp = c.get("/api/domains", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["number"] == 1
    assert body[1]["weight_pct"] == 10


def test_knowledge_points_global(client):
    c, store, db = client
    _seed_globals(db)
    h, _ = _admin(db, store)
    resp = c.get("/api/knowledge-points", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Risk"


def test_books_returns_only_own_org(client):
    c, store, db = client
    # foreign org book
    foreign = Organization(slug="foreign", name="Foreign", kind=OrgKind.personal)
    db.add(foreign); db.flush()
    db.add(Book(organization_id=foreign.id, title="Foreign Book")); db.flush()
    h, _ = _admin(db, store)
    resp = c.get("/api/books", headers=h)
    assert resp.status_code == 200
    assert resp.json() == []


def test_books_and_chapters_own_org(client):
    c, store, db = client
    h, user = _admin(db, store, email="bc@example.com")
    org_id = user.default_organization_id
    book = Book(organization_id=org_id, title="My Book", edition="1e")
    db.add(book); db.flush()
    db.add_all([
        Chapter(organization_id=org_id, book_id=book.id, order_index=2, title="Second"),
        Chapter(organization_id=org_id, book_id=book.id, order_index=1, title="First"),
    ]); db.flush()
    books = c.get("/api/books", headers=h)
    assert books.status_code == 200
    assert [b["title"] for b in books.json()] == ["My Book"]
    chaps = c.get(f"/api/books/{book.id}/chapters", headers=h)
    assert chaps.status_code == 200
    titles = [ch["title"] for ch in chaps.json()]
    assert titles == ["First", "Second"]  # ordered by order_index


def test_chapters_foreign_book_404(client):
    c, store, db = client
    foreign = Organization(slug="fx", name="FX", kind=OrgKind.personal)
    db.add(foreign); db.flush()
    book = Book(organization_id=foreign.id, title="FX Book")
    db.add(book); db.flush()
    h, _ = _admin(db, store, email="fxuser@example.com")
    resp = c.get(f"/api/books/{book.id}/chapters", headers=h)
    assert resp.status_code == 404


def test_unauthenticated_401(client):
    c, _, _ = client
    assert c.get("/api/domains").status_code == 401
    assert c.get("/api/books").status_code == 401
    assert c.get("/api/knowledge-points").status_code == 401
