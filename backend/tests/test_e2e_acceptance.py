"""§14 acceptance E2E paths against the full FastAPI app (real Postgres).

Covers learner practice → answer metadata, fixed exam report, CAT /next,
and analytics dashboard without mocks.
"""

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.db.seed import PERMISSIONS
from app.db.session import get_session
from app.dependencies import get_lockout_store, get_refresh_store
from app.main import create_app
from app.models.auth import OrganizationMembership, Role
from app.models.enums import QuestionType, RoleName
from app.models.question import QuestionMapping
from app.models.taxonomy import ExamBlueprint, ExamDomain, KnowledgePoint
from app.schemas.question import (
    OptionIn,
    QuestionCreateIn,
    ReviewAction,
    TranslationIn,
    TranslationOptionIn,
)
from app.services.auth import InMemoryLockoutStore, register_user
from app.services.question import create_question, submit_review


@pytest.fixture
def client(db_session, session_with_roles):
    app = create_app()
    store = InMemoryRefreshTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: store
    app.dependency_overrides[get_lockout_store] = lambda: InMemoryLockoutStore()
    return TestClient(app), store, db_session


def _headers(db, store, email="e2e@example.com"):
    user, _ = register_user(
        db, email=email, password="pw123456", display_name="E2E", refresh_store=store,
    )
    db.flush()
    role = db.query(Role).filter_by(name=RoleName.individual_learner).first()
    m = db.query(OrganizationMembership).filter_by(user_id=user.id).one()
    m.role_id = role.id
    db.flush()
    token = create_access_token(
        user_id=user.id,
        org_id=user.default_organization_id,
        roles=[RoleName.individual_learner.value],
        perms=[c for c, _ in PERMISSIONS],
    )
    return {"Authorization": f"Bearer {token}"}, user


def _seed_bank(db, user, *, n=3, cat_friendly=False):
    """Publish bilingual questions mapped to a current blueprint domain + KP."""
    bp = ExamBlueprint(
        version_label="e2e-v1",
        effective_date="2026-04-15",
        min_items=1 if not cat_friendly else 2,
        max_items=n if not cat_friendly else max(n, 3),
        duration_minutes=30,
        passing_score=700,
        max_score=1000,
        is_current=True,
    )
    db.add(bp)
    db.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="E2E Domain", weight_pct=100)
    kp = KnowledgePoint(name="E2E KP")
    db.add_all([dom, kp])
    db.flush()
    questions = []
    for i in range(n):
        payload = QuestionCreateIn(
            question_type=QuestionType.single_choice,
            difficulty=3,
            options=[
                OptionIn(order_index=0, is_correct=True),
                OptionIn(order_index=1, is_correct=False),
            ],
            translations=[
                TranslationIn(
                    language="en",
                    stem=f"E2E stem {i}",
                    correct_answer_rationale="rationale",
                    key_point_summary="kp",
                    options=[
                        TranslationOptionIn(order_index=0, content="A", explanation="yes"),
                        TranslationOptionIn(order_index=1, content="B", explanation="no"),
                    ],
                ),
                TranslationIn(
                    language="zh",
                    stem=f"E2E题干{i}",
                    correct_answer_rationale="解析",
                    key_point_summary="要点",
                    options=[
                        TranslationOptionIn(order_index=0, content="甲", explanation="对"),
                        TranslationOptionIn(order_index=1, content="乙", explanation="错"),
                    ],
                ),
            ],
        )
        q = create_question(
            db, org_id=user.default_organization_id, actor_id=user.id, payload=payload,
        )
        db.add(QuestionMapping(
            question_id=q.id, domain_id=dom.id, knowledge_point_id=kp.id,
        ))
        submit_review(
            db, question_id=q.id, actor_id=user.id, action=ReviewAction.submit,
            org_id=user.default_organization_id,
        )
        submit_review(
            db, question_id=q.id, actor_id=user.id, action=ReviewAction.approve,
            org_id=user.default_organization_id,
        )
        questions.append(q)
    db.flush()
    return bp, dom, kp, questions


def test_e2e_practice_answer_state_and_related(client):
    c, store, db = client
    h, user = _headers(db, store, email="e2e-prac@example.com")
    _bp, _dom, kp, questions = _seed_bank(db, user, n=2)

    s = c.post(
        "/api/practice/sessions",
        json={
            "count": 1,
            "order_mode": "sequential",
            "knowledge_point_id": str(kp.id),
            "difficulty": 3,
            "question_type": "single_choice",
        },
        headers=h,
    )
    assert s.status_code == 200, s.text
    sid = s.json()["id"]
    qid = s.json()["config"]["question_ids"][0]

    a = c.post(
        f"/api/practice/sessions/{sid}/answers",
        json={
            "position": 0,
            "selected": [0],
            "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
        headers=h,
    )
    assert a.status_code == 200, a.text
    body = a.json()
    assert body["is_correct"] is True
    assert body["mapping"]["domain_name"] == "E2E Domain"
    assert body["mapping"]["knowledge_point_name"] == "E2E KP"
    assert isinstance(body["history"], list)

    st = c.put(
        f"/api/practice/questions/{qid}/state",
        json={"is_bookmarked": True, "is_questioned": True},
        headers=h,
    )
    assert st.status_code == 200, st.text
    assert st.json()["is_questioned"] is True

    rel = c.get(f"/api/practice/questions/{qid}/related", headers=h)
    assert rel.status_code == 200, rel.text
    related_ids = {item["question_id"] for item in rel.json()}
    assert str(questions[0].id) in related_ids or str(questions[1].id) in related_ids
    assert qid not in related_ids


def test_e2e_fixed_exam_finish_report(client):
    c, store, db = client
    h, user = _headers(db, store, email="e2e-exam@example.com")
    _seed_bank(db, user, n=1)

    created = c.post("/api/exam/sessions", json={"kind": "fixed"}, headers=h)
    assert created.status_code == 200, created.text
    sid = created.json()["id"]

    delivery = c.get(f"/api/exam/sessions/{sid}/questions/0", headers=h)
    assert delivery.status_code == 200, delivery.text
    assert delivery.json()["stem"]["en"]

    ans = c.post(
        f"/api/exam/sessions/{sid}/answers",
        json={
            "position": 0,
            "selected": [0],
            "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
        headers=h,
    )
    assert ans.status_code == 200, ans.text

    fin = c.post(f"/api/exam/sessions/{sid}/finish", headers=h)
    assert fin.status_code == 200, fin.text
    report = c.get(f"/api/exam/sessions/{sid}/report", headers=h)
    assert report.status_code == 200, report.text
    assert "accuracy" in report.json() or "scaled_score" in report.json()


def test_e2e_cat_next_delivers_bilingual(client):
    c, store, db = client
    h, user = _headers(db, store, email="e2e-cat@example.com")
    _seed_bank(db, user, n=5, cat_friendly=True)

    created = c.post(
        "/api/exam/sessions",
        json={"kind": "cat", "language_mode": "bilingual"},
        headers=h,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    sid = body["id"]
    assert body["session_kind"] == "cat"

    nxt = c.get(f"/api/exam/sessions/{sid}/next", headers=h)
    assert nxt.status_code == 200, nxt.text
    body = nxt.json()
    assert body["stem"]["en"]
    assert body["stem"]["zh"]
    assert "en" in body["available_languages"]
    assert "zh" in body["available_languages"]


def test_e2e_analytics_dashboard(client):
    c, store, db = client
    h, _user = _headers(db, store, email="e2e-ana@example.com")
    r = c.get("/api/analytics/dashboard", headers=h)
    assert r.status_code == 200, r.text
    assert "total_answered" in r.json()
