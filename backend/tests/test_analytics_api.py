"""HTTP tests for the analytics API (sub-project H1, Task 6).

Exercises the 7 GET endpoints under /api/analytics:
  dashboard, domains, trend, weak-areas, error-types, recommendation, report.

Auth/RBAC fixture pattern mirrors tests/test_exam_api.py and
tests/test_practice_api.py: the ``client`` fixture returns a
``(TestClient, refresh_store, db_session)`` tuple and ``_headers`` registers a
user + mints a bearer token carrying every permission (incl. practice:read).
All assertions hit the real cissp_test DB (no mocks).
"""

import pytest
from fastapi.testclient import TestClient

from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.db.seed import PERMISSIONS
from app.db.session import get_session
from app.dependencies import get_lockout_store, get_refresh_store
from app.main import create_app
from app.models.auth import OrganizationMembership, Role
from app.models.enums import RoleName
from app.models.taxonomy import ExamBlueprint, ExamDomain
from app.services.auth import InMemoryLockoutStore, register_user


@pytest.fixture
def client(db_session, session_with_roles):
    app = create_app()
    store = InMemoryRefreshTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: store
    app.dependency_overrides[get_lockout_store] = lambda: InMemoryLockoutStore()
    return TestClient(app), store, db_session


def _headers(db_session, store, email="analytics@example.com",
             role=RoleName.individual_learner, perms=None):
    user, _ = register_user(
        db_session, email=email, password="pw123456",
        display_name="L", refresh_store=store,
    )
    db_session.flush()
    r = db_session.query(Role).filter_by(name=role).first()
    m = db_session.query(OrganizationMembership).filter_by(user_id=user.id).one()
    m.role_id = r.id
    db_session.flush()
    if perms is None:
        perms = [c for c, _ in PERMISSIONS]  # all perms, incl. practice:read
    token = create_access_token(
        user_id=user.id, org_id=user.default_organization_id,
        roles=[role.value], perms=perms,
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_current_bp(db, *, n_domains=8, version="analytics-v1"):
    """A current ExamBlueprint with ``n_domains`` ExamDomain rows."""
    bp = ExamBlueprint(
        version_label=version, effective_date="2026-04-15",
        min_items=1, max_items=10, duration_minutes=30,
        passing_score=700, max_score=1000, is_current=True,
    )
    db.add(bp)
    db.flush()
    for n in range(1, n_domains + 1):
        db.add(ExamDomain(
            blueprint_id=bp.id, number=n, name=f"D{n}", weight_pct=12,
        ))
    db.flush()
    return bp


# --------------------------------------------------------------------------- #
# Happy-path / shape (empty user degrades gracefully to 200 zero/empty)
# --------------------------------------------------------------------------- #

def test_dashboard_endpoint(client):
    c, store, db = client
    h = _headers(db, store, email="dash@example.com")
    r = c.get("/api/analytics/dashboard", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["total_answered"] == 0
    assert j["correct_count"] == 0
    assert j["accuracy"] == 0.0
    assert j["study_time_ms"] == 0
    assert j["streak_days"] == 0
    assert j["last_active_at"] is None
    assert j["practiced_questions"] == 0


def test_domains_endpoint(client):
    c, store, db = client
    h = _headers(db, store, email="domains@example.com")
    _seed_current_bp(db)
    r = c.get("/api/analytics/domains", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert isinstance(j, list)
    assert len(j) == 8  # current_bp has 8 domains, ordered by number asc
    assert [d["number"] for d in j] == list(range(1, 9))
    # Empty user -> zero counts, not_started mastery.
    assert all(d["answered"] == 0 for d in j)
    assert all(d["mastery_level"] == "not_started" for d in j)


def test_domains_endpoint_no_blueprint(client):
    """No current blueprint -> /domains returns [] (graceful, 200)."""
    c, store, db = client
    h = _headers(db, store, email="domains-nobp@example.com")
    r = c.get("/api/analytics/domains", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_trend_default_and_invalid(client):
    c, store, db = client
    h = _headers(db, store, email="trend@example.com")
    # default window_days == 30
    r = c.get("/api/analytics/trend", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["window_days"] == 30
    assert j["points"] == []  # empty user
    # 90 is the other allowed window
    r90 = c.get("/api/analytics/trend?window_days=90", headers=h)
    assert r90.status_code == 200, r90.text
    assert r90.json()["window_days"] == 90
    # 7 is rejected -> 422
    r7 = c.get("/api/analytics/trend?window_days=7", headers=h)
    assert r7.status_code == 422


def test_weak_areas_and_error_types(client):
    c, store, db = client
    h = _headers(db, store, email="weak@example.com")
    for path in ("/api/analytics/weak-areas", "/api/analytics/error-types"):
        r = c.get(path, headers=h)
        assert r.status_code == 200, r.text
    # Empty-user shape checks (real service output, not mocks).
    wa = c.get("/api/analytics/weak-areas", headers=h).json()
    assert wa["weak_domains"] == []
    assert wa["weak_knowledge_points"] == []
    et = c.get("/api/analytics/error-types", headers=h).json()
    assert et["total_wrong_classified"] == 0
    # The None ("unclassified") bucket is always present.
    assert {b["error_type"] for b in et["distribution"]} == {None}


def test_recommendation_endpoint(client):
    c, store, db = client
    h = _headers(db, store, email="rec@example.com")
    _seed_current_bp(db)
    r = c.get("/api/analytics/recommendation", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    # Empty user -> no weak areas -> graceful recommendation.
    assert j["focus_domain"] is None
    assert j["next_practice_question_ids"] == []
    assert j["wrong_to_review"] == []
    assert "no weak areas" in j["rationale"].lower()


def test_report_endpoint(client):
    c, store, db = client
    h = _headers(db, store, email="report@example.com")
    _seed_current_bp(db)
    r = c.get("/api/analytics/report", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    # Composition: every PersonalReportOut field present.
    for key in ("generated_at", "dashboard", "domains", "trend_30d",
                "weak_areas", "error_types", "recommendation"):
        assert key in j, key
    # Nested composition: dashboard + recommendation are objects, not null.
    assert isinstance(j["dashboard"], dict)
    assert isinstance(j["recommendation"], dict)
    assert j["dashboard"]["total_answered"] == 0
    assert len(j["domains"]) == 8  # current_bp has 8 domains
    assert j["trend_30d"]["window_days"] == 30
    assert j["generated_at"] is not None


def test_endpoints_require_auth(client):
    """Every endpoint must reject unauthenticated requests with 401."""
    c, store, db = client
    for path in (
        "/api/analytics/dashboard",
        "/api/analytics/domains",
        "/api/analytics/trend",
        "/api/analytics/weak-areas",
        "/api/analytics/error-types",
        "/api/analytics/recommendation",
        "/api/analytics/report",
    ):
        assert c.get(path).status_code == 401, path
