"""FR-IMP-09: question-bank export (CSV template + JSON)."""

import csv
import io
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.questions import router as questions_router
from app.core.security import InMemoryRefreshTokenStore
from app.db.session import get_session
from app.dependencies import get_lockout_store, get_refresh_store
from app.models.enums import RoleName
from app.services.auth import InMemoryLockoutStore

from tests.test_question_api import _headers, _single_body


@pytest.fixture
def client(db_session, session_with_roles):
    app = FastAPI()
    app.include_router(questions_router)
    store = InMemoryRefreshTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: store
    app.dependency_overrides[get_lockout_store] = lambda: InMemoryLockoutStore()
    return TestClient(app), store, db_session


def test_export_csv_round_trips_template(client):
    c, store, db = client
    h = _headers(db, store)
    assert c.post("/api/questions", json=_single_body(), headers=h).status_code == 200

    resp = c.get("/api/questions/export?format=csv", headers=h)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]

    rows = list(csv.DictReader(io.StringIO(resp.content.decode("utf-8-sig"))))
    assert len(rows) == 1
    row = rows[0]
    assert row["question_text"] == "What is 1+1?"
    assert row["option_a"] == "2"
    assert row["correct_answers"] == "A"
    assert row["question_type"] == "single_choice"
    # Every template column is present so the file can feed /api/etl/upload.
    assert set(row.keys()) == {
        "question_text", "question_text_zh", "question_type",
        "option_a", "option_a_zh", "option_b", "option_b_zh",
        "option_c", "option_c_zh", "option_d", "option_d_zh",
        "option_e", "option_e_zh", "option_f", "option_f_zh",
        "correct_answers", "explanation", "explanation_zh",
        "difficulty", "license_status",
        "domain", "knowledge_points", "tags",
        "book", "edition", "chapter", "source",
    }


def test_export_json_carries_full_records(client):
    c, store, db = client
    h = _headers(db, store)
    created = c.post("/api/questions", json=_single_body(), headers=h).json()

    resp = c.get("/api/questions/export?format=json", headers=h)
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert data["exported_at"]
    items = data["items"]
    assert len(items) == 1
    item = items[0]
    assert item["id"] == created["id"]
    assert item["correct_answers"] == ["A"]
    assert item["translations"]["en"]["stem"] == "What is 1+1?"
    assert item["translations"]["en"]["options"][0]["is_correct"] is True


def test_export_respects_status_filter(client):
    c, store, db = client
    h = _headers(db, store)
    c.post("/api/questions", json=_single_body(), headers=h)

    # Nothing is approved yet -> approved-only export is empty.
    resp = c.get("/api/questions/export?status=approved", headers=h)
    rows = list(csv.DictReader(io.StringIO(resp.content.decode("utf-8-sig"))))
    assert rows == []

    resp_all = c.get("/api/questions/export", headers=h)
    rows_all = list(csv.DictReader(io.StringIO(resp_all.content.decode("utf-8-sig"))))
    assert len(rows_all) == 1


def test_export_unknown_status_422(client):
    c, store, db = client
    h = _headers(db, store)
    assert c.get("/api/questions/export?status=nope", headers=h).status_code == 422


def test_export_requires_question_import_permission(client):
    c, store, db = client
    # Perms are loaded fresh from the DB by role, so a learner (no
    # question:import) must be refused: export carries answer keys + licensed
    # content, unlike the question:read list route.
    h_learner = _headers(db, store, email="learner@example.com",
                         role=RoleName.individual_learner)
    assert c.get("/api/questions/export", headers=h_learner).status_code == 403

    h_admin = _headers(db, store, email="exporter@example.com")  # system_admin
    assert c.get("/api/questions/export", headers=h_admin).status_code == 200
