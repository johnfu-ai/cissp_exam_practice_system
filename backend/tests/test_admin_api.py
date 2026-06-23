"""HTTP tests for the admin backoffice router (sub-project H2, Task 9).

Mirrors ``test_exam_api.py``'s auth-fixture conventions: the ``client``
3-tuple (TestClient, refresh store, db_session), a ``_headers`` helper that
registers a user, assigns a role via ``OrganizationMembership``, and mints a
JWT carrying the given perms. Permission gates follow the design spec's
per-endpoint mapping (users/classes=``admin:manage_users``,
cat-params=``admin:manage_taxonomy``, quality=``question:publish``,
audit=``admin:view_audit``, reports=``admin:view_reports``).

Cross-org status codes match the *actual* service behavior (the source of
truth, per the brief): out-of-scope user/class/feedback targets raise
``NotFound`` -> 404; an org_admin supplying another org's ``org_id`` to
``/audit-logs`` or ``/reports/summary`` raises ``ValidationError`` -> 422
(not 403).
"""

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.core.security import InMemoryRefreshTokenStore, create_access_token
from app.db.seed import PERMISSIONS
from app.db.session import get_session
from app.dependencies import get_lockout_store, get_refresh_store
from app.main import create_app
from app.models.admin import AuditLog
from app.models.auth import Organization, OrganizationMembership, Role, User
from app.models.enums import (
    AuditAction,
    OrgKind,
    OrgStatus,
    QuestionFeedbackStatus,
    QuestionFeedbackType,
    QuestionStatus,
    QuestionType,
    RoleName,
    TextFormat,
    UserStatus,
)
from app.models.question import Question, QuestionFeedback, QuestionOption
from app.services.auth import InMemoryLockoutStore, register_user


# org_admin perm set per app/db/seed.py ROLE_PERMISSIONS (no admin:manage_taxonomy).
ORG_ADMIN_PERMS = [
    "question:read", "question:write", "question:publish", "question:import",
    "practice:read", "exam:read", "admin:manage_users", "admin:view_audit",
    "admin:view_reports",
]
LEARNER_PERMS = ["question:read", "practice:read", "exam:read"]


@pytest.fixture
def client(db_session, session_with_roles):
    app = create_app()
    store = InMemoryRefreshTokenStore()
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    app.dependency_overrides[get_refresh_store] = lambda: store
    app.dependency_overrides[get_lockout_store] = lambda: InMemoryLockoutStore()
    return TestClient(app), store, db_session


def _headers(db, store, email, role=RoleName.individual_learner, perms=None):
    """Register a user, set its org-membership role, mint a JWT. Returns
    (headers, user) so callers can read default_organization_id for seeding."""
    user, _ = register_user(
        db, email=email, password="pw123456", display_name="U", refresh_store=store,
    )
    db.flush()
    r = db.query(Role).filter_by(name=role).first()
    m = db.query(OrganizationMembership).filter_by(user_id=user.id).one()
    m.role_id = r.id
    db.flush()
    if perms is None:
        perms = [c for c, _ in PERMISSIONS]
    token = create_access_token(
        user_id=user.id, org_id=user.default_organization_id,
        roles=[role.value], perms=perms,
    )
    return {"Authorization": f"Bearer {token}"}, user


def _question(db, org, actor, stem="q", status=QuestionStatus.published):
    q = Question(
        organization_id=org.id, question_type=QuestionType.single_choice,
        stem=stem, stem_format=TextFormat.markdown, status=status,
        created_by_id=actor.id,
    )
    db.add(q); db.flush()
    db.add(QuestionOption(question_id=q.id, order_index=0, content="A",
                          content_format=TextFormat.markdown, is_correct=True))
    db.add(QuestionOption(question_id=q.id, order_index=1, content="B",
                          content_format=TextFormat.markdown, is_correct=False))
    db.flush()
    return q


def _feedback(db, question, actor, *,
              feedback_type=QuestionFeedbackType.other,
              status=QuestionFeedbackStatus.open, comment="c"):
    fb = QuestionFeedback(
        organization_id=question.organization_id, question_id=question.id,
        reporter_id=actor.id, feedback_type=feedback_type, comment=comment,
        status=status,
    )
    db.add(fb); db.flush()
    return fb


def _audit(db, *, action, org_id, actor_id, entity_type="user", entity_id="x"):
    entry = AuditLog(actor_id=actor_id, organization_id=org_id, action=action,
                     entity_type=entity_type, entity_id=entity_id)
    db.add(entry); db.flush()
    return entry


# ---- FR-ADMIN-03: users ----

def test_users_list_200(client):
    c, store, db = client
    h, admin = _headers(db, store, email="admin@x.com", role=RoleName.system_admin)
    r = c.get("/api/admin/users", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body and "total" in body
    assert any(u["id"] == str(admin.id) for u in body["items"])


def test_users_get_update_status_and_roles_200(client):
    c, store, db = client
    h, _ = _headers(db, store, email="adm1@x.com", role=RoleName.system_admin)
    target, _ = register_user(db, email="tgt@x.com", password="pw123456",
                              display_name="T", refresh_store=store)
    db.flush()
    # get
    g = c.get(f"/api/admin/users/{target.id}", headers=h)
    assert g.status_code == 200, g.text
    assert g.json()["email"] == "tgt@x.com"
    # patch status -> disabled
    s = c.patch(f"/api/admin/users/{target.id}/status",
                json={"status": "disabled"}, headers=h)
    assert s.status_code == 200, s.text
    assert s.json()["status"] == "disabled"
    # put roles -> instructor
    rl = c.put(f"/api/admin/users/{target.id}/roles",
               json={"role_names": ["instructor"]}, headers=h)
    assert rl.status_code == 200, rl.text
    assert rl.json()["roles"] == ["instructor"]


def test_users_401_without_token(client):
    c, _, _ = client
    assert c.get("/api/admin/users").status_code == 401


def test_403_without_perm(client):
    """A learner token (no admin perms) is rejected on every endpoint group."""
    c, store, db = client
    h, _ = _headers(db, store, email="learner@x.com",
                    role=RoleName.individual_learner, perms=LEARNER_PERMS)
    assert c.get("/api/admin/users", headers=h).status_code == 403
    assert c.get("/api/admin/classes", headers=h).status_code == 403
    assert c.get("/api/admin/cat-params", headers=h).status_code == 403
    assert c.get("/api/admin/quality/dashboard", headers=h).status_code == 403
    assert c.get("/api/admin/audit-logs", headers=h).status_code == 403
    assert c.get("/api/admin/reports/summary", headers=h).status_code == 403


def test_users_cross_org_404(client):
    # org_admin (org A) GETting a user in org B -> NotFound -> 404 (not 403),
    # matching the service's _admin_org_scope + out-of-scope -> NotFound rule.
    c, store, db = client
    h, _ = _headers(db, store, email="oa@x.com",
                    role=RoleName.org_admin, perms=ORG_ADMIN_PERMS)
    target, _ = register_user(db, email="o2user@x.com", password="pw123456",
                              display_name="O2", refresh_store=store)
    db.flush()
    assert c.get(f"/api/admin/users/{target.id}", headers=h).status_code == 404


# ---- FR-ADMIN-03: classes ----

def test_class_crud(client):
    c, store, db = client
    h, _ = _headers(db, store, email="c-admin@x.com", role=RoleName.system_admin)
    # create
    cr = c.post("/api/admin/classes", json={"name": "Sec A"}, headers=h)
    assert cr.status_code == 200, cr.text
    cid = cr.json()["id"]
    assert cr.json()["member_count"] == 0
    # get
    assert c.get(f"/api/admin/classes/{cid}", headers=h).status_code == 200
    # update
    up = c.patch(f"/api/admin/classes/{cid}",
                 json={"name": "Sec B"}, headers=h)
    assert up.status_code == 200, up.text
    assert up.json()["name"] == "Sec B"
    # delete -> 204
    assert c.delete(f"/api/admin/classes/{cid}", headers=h).status_code == 204
    # get after delete -> 404
    assert c.get(f"/api/admin/classes/{cid}", headers=h).status_code == 404


def test_class_membership(client):
    c, store, db = client
    h, admin = _headers(db, store, email="m-admin@x.com", role=RoleName.system_admin)
    cid = c.post("/api/admin/classes", json={"name": "Sec M"}, headers=h).json()["id"]
    # a member user in the admin's org (the class's org for system_admin)
    learner_role = db.query(Role).filter_by(name=RoleName.individual_learner).one()
    member = User(email="member@x.com", status=UserStatus.active,
                  default_organization_id=admin.default_organization_id)
    db.add(member); db.flush()
    db.add(OrganizationMembership(user_id=member.id,
          organization_id=admin.default_organization_id, role_id=learner_role.id))
    db.flush()
    # add -> 204
    assert c.post(f"/api/admin/classes/{cid}/members",
                  json={"user_id": str(member.id)}, headers=h).status_code == 204
    # list
    lst = c.get(f"/api/admin/classes/{cid}/members", headers=h)
    assert lst.status_code == 200, lst.text
    assert any(m["user_id"] == str(member.id) for m in lst.json())
    # remove -> 204
    assert c.delete(f"/api/admin/classes/{cid}/members/{member.id}",
                    headers=h).status_code == 204
    lst2 = c.get(f"/api/admin/classes/{cid}/members", headers=h)
    assert all(m["user_id"] != str(member.id) for m in lst2.json())


# ---- FR-ADMIN-04: CAT params ----

def test_cat_params_create_and_set_current(client):
    c, store, db = client
    h, _ = _headers(db, store, email="cat-admin@x.com", role=RoleName.system_admin)
    body = {
        "version_label": "v1", "effective_date": "2026-01-01",
        "params": {"k0": 0.5, "decay": 0.1, "base_se": 1.0, "early_stop_enabled": True},
        "set_current": True,
    }
    r1 = c.post("/api/admin/cat-params", json=body, headers=h)
    assert r1.status_code == 200, r1.text
    assert r1.json()["is_current"] is True
    v1_id = r1.json()["id"]
    # create a second (not current)
    body2 = dict(body, version_label="v2", set_current=False)
    r2 = c.post("/api/admin/cat-params", json=body2, headers=h)
    assert r2.status_code == 200, r2.text
    assert r2.json()["is_current"] is False
    # set v2 current -> v1 loses current
    sc = c.put(f"/api/admin/cat-params/{r2.json()['id']}/current", headers=h)
    assert sc.status_code == 200, sc.text
    assert sc.json()["is_current"] is True
    # list
    lst = c.get("/api/admin/cat-params", headers=h)
    assert lst.status_code == 200, lst.text
    labels = {v["version_label"] for v in lst.json()}
    assert {"v1", "v2"} <= labels
    # v1 no longer current
    v1 = next(v for v in lst.json() if v["version_label"] == "v1")
    assert v1["is_current"] is False
    # duplicate label -> 409
    dup = c.post("/api/admin/cat-params", json=body, headers=h)
    assert dup.status_code == 409


def test_cat_params_invalid_params_422(client):
    c, store, db = client
    h, _ = _headers(db, store, email="cat-422@x.com", role=RoleName.system_admin)
    body = {
        "version_label": "bad", "effective_date": "2026-01-01",
        "params": {"k0": -1.0, "decay": 0.1, "base_se": 1.0},  # k0 <= 0
    }
    assert c.post("/api/admin/cat-params", json=body, headers=h).status_code == 422


# ---- FR-ADMIN-05: quality ----

def test_quality_dashboard_200(client):
    c, store, db = client
    h, _ = _headers(db, store, email="q-admin@x.com", role=RoleName.system_admin)
    actor, _ = register_user(db, email="q-actor@x.com", password="pw123456",
                             display_name="QA", refresh_store=store)
    db.flush()
    org = db.query(Organization).filter_by(id=actor.default_organization_id).one()
    q = _question(db, org, actor, stem="q-fb")
    _feedback(db, q, actor, feedback_type=QuestionFeedbackType.suspected_wrong_answer)
    r = c.get("/api/admin/quality/dashboard", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"open_feedback_count", "low_accuracy_question_count",
            "missing_explanation_count", "disputed_question_count"} <= set(body)
    assert body["open_feedback_count"] >= 1
    assert body["disputed_question_count"] >= 1


def test_quality_feedback_list_and_resolve(client):
    c, store, db = client
    h, _ = _headers(db, store, email="f-admin@x.com", role=RoleName.system_admin)
    actor, _ = register_user(db, email="f-actor@x.com", password="pw123456",
                             display_name="FA", refresh_store=store)
    db.flush()
    org = db.query(Organization).filter_by(id=actor.default_organization_id).one()
    q = _question(db, org, actor, stem="fb-q")
    fb = _feedback(db, q, actor, feedback_type=QuestionFeedbackType.unclear_explanation)
    # list (open)
    lst = c.get("/api/admin/quality/feedback", headers=h)
    assert lst.status_code == 200, lst.text
    assert any(f["id"] == str(fb.id) for f in lst.json()["items"])
    # filter by feedback_type
    ft = c.get("/api/admin/quality/feedback?feedback_type=unclear_explanation", headers=h)
    assert ft.status_code == 200
    assert all(f["feedback_type"] == "unclear_explanation" for f in ft.json()["items"])
    # resolve -> 200
    res = c.patch(f"/api/admin/quality/feedback/{fb.id}",
                  json={"status": "resolved"}, headers=h)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "resolved"


def test_quality_low_accuracy_and_missing_explanations_200(client):
    c, store, db = client
    h, _ = _headers(db, store, email="la-admin@x.com", role=RoleName.system_admin)
    r1 = c.get("/api/admin/quality/low-accuracy", headers=h)
    assert r1.status_code == 200, r1.text
    assert isinstance(r1.json(), list)
    r2 = c.get("/api/admin/quality/missing-explanations", headers=h)
    assert r2.status_code == 200, r2.text
    assert isinstance(r2.json(), list)


# ---- FR-ADMIN-06: audit logs ----

def test_audit_logs_200(client):
    c, store, db = client
    h, admin = _headers(db, store, email="a-admin@x.com", role=RoleName.system_admin)
    _audit(db, action=AuditAction.edit, org_id=admin.default_organization_id,
           actor_id=admin.id, entity_id=str(admin.id))
    r = c.get("/api/admin/audit-logs", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"items", "total", "limit", "offset"} <= set(body)
    assert body["total"] >= 1


def test_audit_logs_action_filter(client):
    c, store, db = client
    h, admin = _headers(db, store, email="af-admin@x.com", role=RoleName.system_admin)
    _audit(db, action=AuditAction.edit, org_id=admin.default_organization_id, actor_id=admin.id)
    _audit(db, action=AuditAction.publish, org_id=admin.default_organization_id, actor_id=admin.id)
    r = c.get("/api/admin/audit-logs?action=edit", headers=h)
    assert r.status_code == 200, r.text
    assert all(i["action"] == "edit" for i in r.json()["items"])


# ---- FR-ADMIN-07: reports ----

def test_report_summary_default_200(client):
    c, store, db = client
    h, _ = _headers(db, store, email="r-admin@x.com", role=RoleName.system_admin)
    r = c.get("/api/admin/reports/summary", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["window_days"] == 30
    assert body["scope"] == "global"  # system_admin, no org_id


def test_report_summary_invalid_window_422(client):
    c, store, db = client
    h, _ = _headers(db, store, email="rw-admin@x.com", role=RoleName.system_admin)
    r = c.get("/api/admin/reports/summary?window_days=7", headers=h)
    assert r.status_code == 422, r.text
    # 90 is valid
    assert c.get("/api/admin/reports/summary?window_days=90", headers=h).status_code == 200


def test_report_summary_org_admin_cross_org_422(client):
    # org_admin (org A) requesting another org's id -> ValidationError -> 422
    # (the service treats this as a param-validation error, not a target
    # lookup, so it is 422 not 404/403 — matches report_summary's behavior).
    c, store, db = client
    h, _ = _headers(db, store, email="roa@x.com",
                    role=RoleName.org_admin, perms=ORG_ADMIN_PERMS)
    other = Organization(name="other", slug="other-org",
                         kind=OrgKind.personal, status=OrgStatus.active)
    db.add(other); db.flush()
    r = c.get(f"/api/admin/reports/summary?org_id={other.id}", headers=h)
    assert r.status_code == 422, r.text


def test_audit_logs_org_admin_cross_org_422(client):
    # org_admin passing a different org_id to /audit-logs -> 422 (param error).
    c, store, db = client
    h, _ = _headers(db, store, email="aoa@x.com",
                    role=RoleName.org_admin, perms=ORG_ADMIN_PERMS)
    other = Organization(name="other2", slug="other-org2",
                         kind=OrgKind.personal, status=OrgStatus.active)
    db.add(other); db.flush()
    r = c.get(f"/api/admin/audit-logs?org_id={other.id}", headers=h)
    assert r.status_code == 422, r.text
