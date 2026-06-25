"""Question bank HTTP API tests (translations-based).

The ``client`` fixture builds a minimal FastAPI app mounting only the questions
router. The full ``create_app()`` cannot be used yet because sibling services
(``app.services.admin``/``exam``/``practice`` and ``app.etl``) still import the
removed ``Explanation`` model and are rewritten in later tasks (T5/T6/T8/T9).
Once those land, this can revert to ``create_app()``.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.questions import router as questions_router
from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.db.seed import PERMISSIONS
from app.db.session import get_session
from app.dependencies import get_lockout_store, get_refresh_store
from app.models.auth import OrganizationMembership, Role
from app.models.enums import RoleName
from app.services.auth import InMemoryLockoutStore, register_user


@pytest.fixture
def client(db_session, session_with_roles):
    app = FastAPI()
    app.include_router(questions_router)
    store = InMemoryRefreshTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: store
    app.dependency_overrides[get_lockout_store] = lambda: InMemoryLockoutStore()
    return TestClient(app), store, db_session


def _headers(db_session, store, email="q@example.com", role=RoleName.system_admin,
             perms=None):
    user, _ = register_user(db_session, email=email, password="pw123456",
                            display_name="Q", refresh_store=store)
    db_session.flush()
    r = db_session.query(Role).filter_by(name=role).first()
    m = db_session.query(OrganizationMembership).filter_by(user_id=user.id).one()
    m.role_id = r.id
    db_session.flush()
    if perms is None:
        perms = [c for c, _ in PERMISSIONS]
    token = create_access_token(user_id=user.id, org_id=user.default_organization_id,
                                roles=[role.value], perms=perms)
    return {"Authorization": f"Bearer {token}"}


def _single_body():
    return {
        "question_type": "single_choice",
        "options": [
            {"order_index": 0, "is_correct": True},
            {"order_index": 1, "is_correct": False},
        ],
        "translations": [{
            "language": "en", "stem": "What is 1+1?", "correct_answer_rationale": "2",
            "options": [
                {"order_index": 0, "content": "2"},
                {"order_index": 1, "content": "3"},
            ],
        }],
    }


def _bilingual_body():
    body = _single_body()
    body["translations"].append({
        "language": "zh", "stem": "1+1等于几？", "correct_answer_rationale": "因为等于2",
        "options": [
            {"order_index": 0, "content": "2"},
            {"order_index": 1, "content": "3"},
        ],
    })
    return body


def test_create_and_get(client):
    c, store, db = client
    h = _headers(db, store, email="c1@example.com")
    resp = c.post("/api/questions", json=_single_body(), headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    qid = body["id"]
    assert body["status"] == "draft"
    assert body["available_languages"] == ["en"]
    assert len(body["options"]) == 2
    assert len(body["translations"]) == 1
    assert body["translations"][0]["stem"] == "What is 1+1?"
    got = c.get(f"/api/questions/{qid}", headers=h)
    assert got.status_code == 200
    assert len(got.json()["options"]) == 2
    assert len(got.json()["translations"]) == 1


def test_create_validation_422(client):
    c, store, db = client
    h = _headers(db, store, email="c2@example.com")
    body = _single_body()
    body["options"][0]["is_correct"] = False
    body["options"][1]["is_correct"] = False
    assert c.post("/api/questions", json=body, headers=h).status_code == 422


def test_list_and_paginate(client):
    c, store, db = client
    h = _headers(db, store, email="l@example.com")
    for _ in range(3):
        c.post("/api/questions", json=_single_body(), headers=h)
    resp = c.get("/api/questions?page=1&size=2", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["items"][0]["available_languages"] == ["en"]


def test_list_missing_language_filter(client):
    c, store, db = client
    h = _headers(db, store, email="ml@example.com")
    # en-only
    c.post("/api/questions", json=_single_body(), headers=h)
    # bilingual
    c.post("/api/questions", json=_bilingual_body(), headers=h)
    resp = c.get("/api/questions?missing_language=zh", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["available_languages"] == ["en"]


def test_update_then_revisions(client):
    c, store, db = client
    h = _headers(db, store, email="u@example.com")
    qid = c.post("/api/questions", json=_single_body(), headers=h).json()["id"]
    put = c.put(f"/api/questions/{qid}", json={"translations": [{
        "language": "en", "stem": "What is 2+2?", "correct_answer_rationale": "4",
        "options": [{"order_index": 0, "content": "4"}, {"order_index": 1, "content": "5"}],
    }]}, headers=h)
    assert put.status_code == 200, put.text
    assert put.json()["version"] == 2
    revs = c.get(f"/api/questions/{qid}/revisions", headers=h)
    assert revs.status_code == 200
    assert len(revs.json()) == 2


def test_review_lifecycle(client):
    c, store, db = client
    h = _headers(db, store, email="r@example.com")
    qid = c.post("/api/questions", json=_single_body(), headers=h).json()["id"]
    assert c.post(f"/api/questions/{qid}/review", json={"action": "submit"}, headers=h).status_code == 200
    assert c.post(f"/api/questions/{qid}/review", json={"action": "approve"}, headers=h).status_code == 200
    got = c.get(f"/api/questions/{qid}", headers=h)
    assert got.json()["status"] == "published"


def test_review_illegal_transition_409(client):
    c, store, db = client
    h = _headers(db, store, email="ri@example.com")
    qid = c.post("/api/questions", json=_single_body(), headers=h).json()["id"]
    resp = c.post(f"/api/questions/{qid}/review", json={"action": "approve"}, headers=h)
    assert resp.status_code == 409


def test_delete_then_404(client):
    c, store, db = client
    h = _headers(db, store, email="d@example.com")
    qid = c.post("/api/questions", json=_single_body(), headers=h).json()["id"]
    assert c.delete(f"/api/questions/{qid}", headers=h).status_code == 200
    assert c.get(f"/api/questions/{qid}", headers=h).status_code == 404


def test_feedback_create_and_list(client):
    c, store, db = client
    h = _headers(db, store, email="f@example.com")
    qid = c.post("/api/questions", json=_single_body(), headers=h).json()["id"]
    resp = c.post(f"/api/questions/{qid}/feedback",
                  json={"feedback_type": "unclear_explanation", "comment": "huh?"},
                  headers=h)
    assert resp.status_code == 200
    lst = c.get(f"/api/questions/{qid}/feedback", headers=h)
    assert lst.status_code == 200
    assert len(lst.json()) == 1


def test_unauthenticated_401(client):
    c, _, _ = client
    assert c.get("/api/questions").status_code == 401


def test_learner_cannot_create_403(client):
    c, store, db = client
    h = _headers(db, store, email="no@example.com", role=RoleName.individual_learner,
                 perms=["question:read", "practice:read", "exam:read"])
    assert c.post("/api/questions", json=_single_body(), headers=h).status_code == 403


def test_editor_can_write_and_publish(client):
    c, store, db = client
    h = _headers(db, store, email="ed@example.com", role=RoleName.content_editor,
                 perms=["question:read", "question:write", "question:publish", "question:import"])
    qid = c.post("/api/questions", json=_single_body(), headers=h).json()["id"]
    c.post(f"/api/questions/{qid}/review", json={"action": "submit"}, headers=h)
    assert c.post(f"/api/questions/{qid}/review", json={"action": "approve"}, headers=h).status_code == 200


def test_language_coverage(client):
    c, store, db = client
    h = _headers(db, store, email="cov@example.com")
    # en-only
    c.post("/api/questions", json=_single_body(), headers=h)
    # bilingual
    c.post("/api/questions", json=_bilingual_body(), headers=h)
    resp = c.get("/api/questions/language-coverage", headers=h)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["en_only"] == 1
    assert data["both"] == 1
    assert data["zh_only"] == 0
    assert data["neither"] == 0
    assert data["total"] == 2


def test_language_coverage_requires_reports_perm(client):
    c, store, db = client
    h = _headers(db, store, email="nocov@example.com", role=RoleName.individual_learner,
                 perms=["question:read", "practice:read", "exam:read"])
    assert c.get("/api/questions/language-coverage", headers=h).status_code == 403
