"""Service-layer tests for admin backoffice (sub-project H2, Task 4).

Covers user management + class management (FR-ADMIN-03). Seeds orgs/users on
the real ``cissp_test`` DB using module-level helpers matching
``test_exam_service.py`` / ``test_analytics.py`` conventions. Uses the
``session_with_roles`` fixture so every ``RoleName`` row + the permission
matrix already exist for ``OrganizationMembership`` and role lookups.
"""

import pytest
from datetime import date, datetime, timezone

from app.db.seed import PERMISSIONS
from app.dependencies import CurrentUser
from app.models.admin import AuditLog, CatParamsVersion
from app.models.auth import (
    Organization,
    OrganizationMembership,
    Role,
    RoleName,
    User,
)
from app.models.enums import (
    AuditAction,
    OrgKind,
    OrgStatus,
    PracticeSessionStatus,
    QuestionFeedbackStatus,
    QuestionFeedbackType,
    QuestionStatus,
    QuestionType,
    TextFormat,
    UserStatus,
)
from app.models.practice import PracticeAnswer, PracticeSession
from app.models.question import Explanation, Question, QuestionFeedback, QuestionOption
from app.schemas.admin import CatParams, CatParamsIn, ClassIn, FeedbackResolveIn
from app.services import admin as svc


def _org(db, slug):
    o = Organization(name=slug, slug=slug, kind=OrgKind.personal, status=OrgStatus.active)
    db.add(o); db.flush(); return o


def _user(db, email, org, status=UserStatus.active):
    u = User(email=email, status=status, default_organization_id=org.id)
    db.add(u); db.flush()
    db.add(OrganizationMembership(user_id=u.id, organization_id=org.id,
            role_id=db.query(Role).filter_by(name=RoleName.individual_learner).one().id))
    db.flush(); return u


def _current(db, org, role_name=RoleName.org_admin):
    role = db.query(Role).filter_by(name=role_name).one()
    return CurrentUser(user=_user(db, f"admin-{org.slug}@x.com", org),
                       org_id=org.id, roles=[role_name.value],
                       perms=[c for c, _ in PERMISSIONS])


def test_list_users_org_scoped(session_with_roles):
    db = session_with_roles
    o1, o2 = _org(db, "o1"), _org(db, "o2")
    _user(db, "a@x.com", o1); _user(db, "b@x.com", o2)
    cur = _current(db, o1)
    users, total = svc.list_users(db, current=cur, search=None, limit=50, offset=0)
    emails = {u.email for u in users}
    assert "a@x.com" in emails and "b@x.com" not in emails
    assert total >= 1


def test_org_admin_cannot_get_other_org_user(session_with_roles):
    db = session_with_roles
    o1, o2 = _org(db, "o1"), _org(db, "o2")
    target = _user(db, "x@x.com", o2)
    cur = _current(db, o1)
    with pytest.raises(svc.NotFound):
        svc.get_user(db, current=cur, user_id=target.id)


def test_set_user_status_audits(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    target = _user(db, "t@x.com", o1)
    cur = _current(db, o1)
    out = svc.set_user_status(db, current=cur, user_id=target.id, status=UserStatus.disabled)
    assert out.status == "disabled"
    db.flush()
    from app.models.admin import AuditLog
    logs = db.query(AuditLog).filter_by(entity_type="user", entity_id=str(target.id)).all()
    assert any(l.action.value == "permission_change" for l in logs)


def test_set_user_roles_scoped_to_org(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    target = _user(db, "t@x.com", o1)
    cur = _current(db, o1)
    out = svc.set_user_roles(db, current=cur, user_id=target.id,
                             role_names=[RoleName.instructor])
    assert out.roles == ["instructor"]
    # membership role updated
    m = db.query(OrganizationMembership).filter_by(user_id=target.id, organization_id=o1.id).one()
    assert m.role_id == db.query(Role).filter_by(name=RoleName.instructor).one().id


def test_class_crud_org_scoped(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _current(db, o1)
    c = svc.create_class(db, current=cur, payload=ClassIn(name="Sec A"))
    assert c.organization_id == o1.id
    got = svc.get_class(db, current=cur, class_id=c.id)
    assert got.name == "Sec A"
    upd = svc.update_class(db, current=cur, class_id=c.id,
                           payload=ClassIn(name="Sec B"))
    assert upd.name == "Sec B"
    svc.delete_class(db, current=cur, class_id=c.id)
    with pytest.raises(svc.NotFound):
        svc.get_class(db, current=cur, class_id=c.id)


def test_class_membership(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    target = _user(db, "m@x.com", o1)
    cur = _current(db, o1)
    c = svc.create_class(db, current=cur, payload=ClassIn(name="Sec A"))
    svc.add_class_member(db, current=cur, class_id=c.id, user_id=target.id)
    members = svc.list_class_members(db, current=cur, class_id=c.id)
    assert any(m.user_id == target.id for m in members)
    svc.remove_class_member(db, current=cur, class_id=c.id, user_id=target.id)
    assert not any(m.user_id == target.id for m in svc.list_class_members(db, current=cur, class_id=c.id))


def test_get_user_with_multiple_roles_in_same_org(session_with_roles):
    """Regression: a user with 2+ roles in the same org has multiple
    OrganizationMembership rows. get_user's org-scope existence check must use
    .first() (not .scalar_one_or_none()), which otherwise raises
    sqlalchemy.exc.MultipleResultsFound -> 500. set_user_roles itself creates
    such multi-role memberships, so this path is reachable in production."""
    db = session_with_roles
    o1 = _org(db, "o1")
    target = _user(db, "multi@x.com", o1)
    cur = _current(db, o1)
    # Give the target TWO roles in the same org -> two OrganizationMembership
    # rows for (user_id, organization_id) with different role_id.
    svc.set_user_roles(db, current=cur, user_id=target.id,
                       role_names=[RoleName.instructor, RoleName.content_editor])
    memberships = db.query(OrganizationMembership).filter_by(
        user_id=target.id, organization_id=o1.id).all()
    assert len(memberships) == 2  # sanity: the bug precondition holds

    # Before the fix this raised MultipleResultsFound (a 500 in the router).
    out = svc.get_user(db, current=cur, user_id=target.id)
    assert out.id == target.id
    assert set(out.roles) == {"instructor", "content_editor"}


# ---- FR-ADMIN-04: CAT params ----

def _sysadmin_current(db, org):
    return _current(db, org, role_name=RoleName.system_admin)


def test_create_cat_params_sets_current_and_unsets_siblings(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _sysadmin_current(db, o1)
    v1 = svc.create_cat_params(db, current=cur, payload=CatParamsIn(
        version_label="v1", effective_date=date(2026, 1, 1),
        params=CatParams(k0=0.5, decay=0.1, base_se=1.0)))
    assert v1.is_current is True
    v2 = svc.create_cat_params(db, current=cur, payload=CatParamsIn(
        version_label="v2", effective_date=date(2026, 2, 1),
        params=CatParams(k0=0.4, decay=0.1, base_se=1.0)))
    db.flush()
    assert v2.is_current is True
    assert db.get(CatParamsVersion, v1.id).is_current is False


def test_set_current_cat_params(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _sysadmin_current(db, o1)
    v1 = svc.create_cat_params(db, current=cur, payload=CatParamsIn(
        version_label="v1", effective_date=date(2026, 1, 1),
        params=CatParams(k0=0.5, decay=0.1, base_se=1.0), set_current=False))
    v2 = svc.create_cat_params(db, current=cur, payload=CatParamsIn(
        version_label="v2", effective_date=date(2026, 2, 1),
        params=CatParams(k0=0.4, decay=0.1, base_se=1.0), set_current=True))
    out = svc.set_current_cat_params(db, current=cur, version_id=v1.id)
    assert out.is_current is True
    assert db.get(CatParamsVersion, v2.id).is_current is False


def test_get_current_cat_params_fallback_none(session_with_roles):
    db = session_with_roles
    assert svc.get_current_cat_params(db) is None


def test_create_cat_params_duplicate_label_conflict(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _sysadmin_current(db, o1)
    svc.create_cat_params(db, current=cur, payload=CatParamsIn(
        version_label="v1", effective_date=date(2026, 1, 1),
        params=CatParams(k0=0.5, decay=0.1, base_se=1.0)))
    with pytest.raises(svc.ConflictError):
        svc.create_cat_params(db, current=cur, payload=CatParamsIn(
            version_label="v1", effective_date=date(2026, 2, 1),
            params=CatParams(k0=0.4, decay=0.1, base_se=1.0)))


def test_set_current_cat_params_unknown_id_not_found(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _sysadmin_current(db, o1)
    import uuid as _uuid
    with pytest.raises(svc.NotFound):
        svc.set_current_cat_params(db, current=cur, version_id=_uuid.uuid4())


def test_create_cat_params_audits_config_change(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _sysadmin_current(db, o1)
    v1 = svc.create_cat_params(db, current=cur, payload=CatParamsIn(
        version_label="v1", effective_date=date(2026, 1, 1),
        params=CatParams(k0=0.5, decay=0.1, base_se=1.0)))
    db.flush()
    from app.models.admin import AuditLog
    logs = db.query(AuditLog).filter_by(
        entity_type="cat_params", entity_id=str(v1.id)).all()
    assert any(l.action.value == "config_change" for l in logs)
    assert all(l.organization_id is None for l in logs)


# ---- FR-ADMIN-05: content quality queue ----
#
# Seed helpers mirror the conventions in test_analytics.py
# (_question / _practice_session / _practice_answer) but live here so the
# admin tests stay self-contained.

def _question(db, org, actor, *, stem="q", status=QuestionStatus.published):
    """Single-choice question with option 0 correct, option 1 wrong."""
    q = Question(
        organization_id=org.id,
        question_type=QuestionType.single_choice,
        stem=stem,
        stem_format=TextFormat.markdown,
        status=status,
        created_by_id=actor.id,
    )
    db.add(q); db.flush()
    db.add(QuestionOption(
        question_id=q.id, order_index=0, content="A",
        content_format=TextFormat.markdown, is_correct=True,
    ))
    db.add(QuestionOption(
        question_id=q.id, order_index=1, content="B",
        content_format=TextFormat.markdown, is_correct=False,
    ))
    db.flush()
    return q


def _practice_session(db, org, actor):
    s = PracticeSession(
        user_id=actor.id,
        organization_id=org.id,
        status=PracticeSessionStatus.completed,
        total_questions=1,
    )
    db.add(s); db.flush()
    return s


def _practice_answer(db, *, session, actor, question, is_correct):
    ans = PracticeAnswer(
        session_id=session.id,
        user_id=actor.id,
        question_id=question.id,
        question_snapshot={},
        options_snapshot=[],
        user_answer={"selected": [0]},
        is_correct=is_correct,
        time_spent_ms=1000,
        answered_at=datetime.now(timezone.utc),
    )
    db.add(ans); db.flush()
    return ans


def _feedback(db, question, actor, *,
              feedback_type=QuestionFeedbackType.other,
              status=QuestionFeedbackStatus.open, comment="c"):
    fb = QuestionFeedback(
        organization_id=question.organization_id,
        question_id=question.id,
        reporter_id=actor.id,
        feedback_type=feedback_type,
        comment=comment,
        status=status,
    )
    db.add(fb); db.flush()
    return fb


def test_quality_dashboard_counts(session_with_roles):
    # seed: 1 open feedback, 1 low-acc question (answered>=5, acc<0.6),
    # 1 published question with no Explanation, 1 disputed (open
    # suspected_wrong_answer).
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _current(db, o1)
    actor = cur.user
    ps = _practice_session(db, o1, actor)
    # disputed: open suspected_wrong_answer feedback (also counts as open)
    q_disputed = _question(db, o1, actor, stem="disputed")
    _feedback(db, q_disputed, actor,
              feedback_type=QuestionFeedbackType.suspected_wrong_answer)
    # low-acc: 5 answers, 1 correct (acc 0.2 < 0.6)
    q_low = _question(db, o1, actor, stem="low")
    for i in range(5):
        _practice_answer(db, session=ps, actor=actor, question=q_low,
                         is_correct=(i == 0))
    # missing-explanation: published question with no Explanation row
    q_missing = _question(db, o1, actor, stem="missing")
    assert db.query(Explanation).filter_by(question_id=q_missing.id).count() == 0
    out = svc.quality_dashboard(db, current=cur)
    assert out.open_feedback_count >= 1
    assert out.disputed_question_count >= 1
    assert out.low_accuracy_question_count >= 1
    assert out.missing_explanation_count >= 1


def test_resolve_feedback(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _current(db, o1)
    actor = cur.user
    q = _question(db, o1, actor, stem="fb-q")
    fb = _feedback(db, q, actor,
                   feedback_type=QuestionFeedbackType.unclear_explanation)
    out = svc.resolve_feedback(db, current=cur, feedback_id=fb.id,
                               payload=FeedbackResolveIn(
                                   status=QuestionFeedbackStatus.resolved))
    assert out.status == "resolved"
    assert out.id == fb.id
    db.flush()
    from app.models.admin import AuditLog
    logs = db.query(AuditLog).filter_by(
        entity_type="feedback", entity_id=str(fb.id)).all()
    assert any(l.action.value == "edit" for l in logs)
    assert all(l.organization_id == o1.id for l in logs)


def test_resolve_feedback_out_of_scope_not_found(session_with_roles):
    # Out-of-scope feedback resolves to NotFound (not 403) — binding rule.
    db = session_with_roles
    o1, o2 = _org(db, "o1"), _org(db, "o2")
    cur_o1 = _current(db, o1)
    actor_o2 = _user(db, "o2-user@x.com", o2)
    q_o2 = _question(db, o2, actor_o2, stem="o2-fb-q")
    fb = _feedback(db, q_o2, actor_o2,
                   feedback_type=QuestionFeedbackType.unclear_explanation)
    with pytest.raises(svc.NotFound):
        svc.resolve_feedback(db, current=cur_o1, feedback_id=fb.id,
                             payload=FeedbackResolveIn(
                                 status=QuestionFeedbackStatus.resolved))


def test_low_accuracy_threshold_and_order(session_with_roles):
    # a question answered 5x with 1 correct (acc 0.2) and one answered 4x
    # (below threshold).
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _current(db, o1)
    actor = cur.user
    ps = _practice_session(db, o1, actor)
    # q_below: 4 answers -> below the answered>=5 threshold (excluded)
    q_below = _question(db, o1, actor, stem="below")
    for _ in range(4):
        _practice_answer(db, session=ps, actor=actor, question=q_below,
                         is_correct=False)
    # q_low: 5 answers, 1 correct -> acc 0.2 (low)
    q_low = _question(db, o1, actor, stem="low")
    for i in range(5):
        _practice_answer(db, session=ps, actor=actor, question=q_low,
                         is_correct=(i == 0))
    # q_zero: 5 answers, 0 correct -> acc 0.0 (lowest)
    q_zero = _question(db, o1, actor, stem="zero")
    for _ in range(5):
        _practice_answer(db, session=ps, actor=actor, question=q_zero,
                         is_correct=False)
    rows = svc.list_low_accuracy_questions(db, current=cur, limit=10)
    assert all(r.accuracy < 0.6 and r.answered >= 5 for r in rows)
    assert rows == sorted(rows, key=lambda r: r.accuracy)
    # q_below (4 answered) is excluded
    assert all(r.question_id != q_below.id for r in rows)
    # q_low and q_zero are included
    ids = {r.question_id for r in rows}
    assert q_low.id in ids
    assert q_zero.id in ids


def test_quality_org_scoped(session_with_roles):
    # feedback in o2 invisible to o1 admin; o1 feedback visible.
    db = session_with_roles
    o1, o2 = _org(db, "o1"), _org(db, "o2")
    cur_o1 = _current(db, o1)
    actor_o1 = cur_o1.user
    actor_o2 = _user(db, "o2-user@x.com", o2)
    q_o1 = _question(db, o1, actor_o1, stem="o1-q")
    _feedback(db, q_o1, actor_o1,
              feedback_type=QuestionFeedbackType.unclear_explanation)
    q_o2 = _question(db, o2, actor_o2, stem="o2-q")
    _feedback(db, q_o2, actor_o2,
              feedback_type=QuestionFeedbackType.unclear_explanation)
    rows, total = svc.list_open_feedback(db, current=cur_o1, feedback_type=None,
                                         limit=50, offset=0)
    assert all(r.question_id != q_o2.id for r in rows)
    assert any(r.question_id == q_o1.id for r in rows)
    assert total >= 1


# ---- FR-ADMIN-06: audit log viewer ----
#
# list_audit_logs: org_admin sees only own org; system_admin sees all (incl.
# organization_id=None system events); org_id param forbidden for org_admin
# when different from own, and filters for system_admin. Supports action /
# actor_id / entity_type / since / until filters and limit/offset pagination.

def _audit(db, *, action, org_id, actor_id=None, entity_type="user",
           entity_id="x", occurred_at=None, details=None, ip_address=None):
    """Direct AuditLog insert. occurred_at is set explicitly for time-filter
    tests (log_audit doesn't accept it and relies on the now() server default,
    which is unsuitable when a test needs deterministic timestamps)."""
    entry = AuditLog(
        actor_id=actor_id,
        organization_id=org_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address,
    )
    if occurred_at is not None:
        entry.occurred_at = occurred_at
    db.add(entry); db.flush()
    return entry


def test_audit_logs_org_scoped(session_with_roles):
    # org_admin sees only own org's logs; o2's logs are invisible. Omitting
    # org_id defaults to the admin's own org.
    db = session_with_roles
    o1, o2 = _org(db, "o1"), _org(db, "o2")
    cur_o1 = _current(db, o1)
    a1 = cur_o1.user
    a2 = _user(db, "o2-actor@x.com", o2)
    _audit(db, action=AuditAction.edit, org_id=o1.id, actor_id=a1.id, entity_id=str(a1.id))
    _audit(db, action=AuditAction.edit, org_id=o2.id, actor_id=a2.id, entity_id=str(a2.id))
    out = svc.list_audit_logs(db, current=cur_o1)
    assert all(i.organization_id == o1.id for i in out.items)
    assert all(i.organization_id != o2.id for i in out.items)
    assert out.total >= 1
    assert out.limit == 50 and out.offset == 0


def test_audit_logs_action_filter(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _sysadmin_current(db, o1)
    a = cur.user
    _audit(db, action=AuditAction.edit, org_id=o1.id, actor_id=a.id)
    _audit(db, action=AuditAction.publish, org_id=o1.id, actor_id=a.id)
    out = svc.list_audit_logs(db, current=cur, action=AuditAction.edit)
    assert out.total >= 1
    assert all(i.action == "edit" for i in out.items)


def test_audit_logs_system_admin_sees_all_including_system_events(session_with_roles):
    # system_admin (scope None) sees every org's logs AND organization_id=None
    # system-level events (e.g. CAT params config_change per FR-ADMIN-04).
    db = session_with_roles
    o1, o2 = _org(db, "o1"), _org(db, "o2")
    cur = _sysadmin_current(db, o1)
    a = cur.user
    _audit(db, action=AuditAction.edit, org_id=o1.id, actor_id=a.id)
    _audit(db, action=AuditAction.edit, org_id=o2.id, actor_id=a.id)
    _audit(db, action=AuditAction.config_change, org_id=None, actor_id=a.id,
           entity_type="cat_params")
    out = svc.list_audit_logs(db, current=cur)
    orgs = {i.organization_id for i in out.items}
    assert o1.id in orgs and o2.id in orgs
    assert None in orgs  # system-level event visible to system_admin
    assert out.total >= 3


def test_audit_logs_system_admin_org_id_param_filters(session_with_roles):
    # For system_admin the org_id param further filters (does not forbid).
    db = session_with_roles
    o1, o2 = _org(db, "o1"), _org(db, "o2")
    cur = _sysadmin_current(db, o1)
    a = cur.user
    _audit(db, action=AuditAction.edit, org_id=o1.id, actor_id=a.id)
    _audit(db, action=AuditAction.edit, org_id=o2.id, actor_id=a.id)
    out = svc.list_audit_logs(db, current=cur, org_id=o1.id)
    assert all(i.organization_id == o1.id for i in out.items)
    assert all(i.organization_id != o2.id for i in out.items)


def test_audit_logs_org_admin_forbidden_other_org(session_with_roles):
    # org_admin passing a different org_id raises ValidationError (not NotFound
    # — this is a param validation, not a target lookup).
    db = session_with_roles
    o1, o2 = _org(db, "o1"), _org(db, "o2")
    cur_o1 = _current(db, o1)
    with pytest.raises(svc.ValidationError):
        svc.list_audit_logs(db, current=cur_o1, org_id=o2.id)


def test_audit_logs_actor_and_entity_filters(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _sysadmin_current(db, o1)
    a = cur.user
    other = _user(db, "other@x.com", o1)
    _audit(db, action=AuditAction.edit, org_id=o1.id, actor_id=a.id,
           entity_type="user", entity_id="u1")
    _audit(db, action=AuditAction.edit, org_id=o1.id, actor_id=other.id,
           entity_type="class", entity_id="c1")
    out_actor = svc.list_audit_logs(db, current=cur, actor_id=a.id)
    assert all(i.actor_id == a.id for i in out_actor.items)
    out_entity = svc.list_audit_logs(db, current=cur, entity_type="class")
    assert all(i.entity_type == "class" for i in out_entity.items)


def test_audit_logs_since_until_time_filter(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _sysadmin_current(db, o1)
    a = cur.user
    t_old = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t_mid = datetime(2026, 6, 1, tzinfo=timezone.utc)
    t_new = datetime(2026, 12, 1, tzinfo=timezone.utc)
    e_old = _audit(db, action=AuditAction.edit, org_id=o1.id, actor_id=a.id, occurred_at=t_old)
    e_mid = _audit(db, action=AuditAction.edit, org_id=o1.id, actor_id=a.id, occurred_at=t_mid)
    e_new = _audit(db, action=AuditAction.edit, org_id=o1.id, actor_id=a.id, occurred_at=t_new)
    out = svc.list_audit_logs(db, current=cur,
                              since=datetime(2026, 3, 1, tzinfo=timezone.utc),
                              until=datetime(2026, 9, 1, tzinfo=timezone.utc))
    ids = {i.id for i in out.items}
    assert e_mid.id in ids
    assert e_old.id not in ids
    assert e_new.id not in ids


def test_audit_logs_pagination(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _sysadmin_current(db, o1)
    a = cur.user
    for i in range(5):
        _audit(db, action=AuditAction.edit, org_id=o1.id, actor_id=a.id, entity_id=str(i))
    page1 = svc.list_audit_logs(db, current=cur, limit=2, offset=0)
    page2 = svc.list_audit_logs(db, current=cur, limit=2, offset=2)
    assert len(page1.items) == 2
    assert len(page2.items) == 2
    assert page1.total == page2.total
    assert page1.total >= 5
    # pages must not overlap
    p1_ids = {i.id for i in page1.items}
    p2_ids = {i.id for i in page2.items}
    assert not (p1_ids & p2_ids)
    assert page1.limit == 2 and page1.offset == 0
    assert page2.limit == 2 and page2.offset == 2


def test_audit_logs_output_mapping(session_with_roles):
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _sysadmin_current(db, o1)
    a = cur.user
    entry = _audit(db, action=AuditAction.edit, org_id=o1.id, actor_id=a.id,
                   entity_type="user", entity_id=str(a.id),
                   details={"k": "v"}, ip_address="10.0.0.1")
    out = svc.list_audit_logs(db, current=cur)
    match = next(i for i in out.items if i.id == entry.id)
    assert match.action == "edit"
    assert match.actor_id == a.id
    assert match.organization_id == o1.id
    assert match.entity_type == "user"
    assert match.entity_id == str(a.id)
    assert match.details == {"k": "v"}
    assert match.ip_address == "10.0.0.1"
    assert match.occurred_at is not None


def test_audit_logs_sees_service_emitted_rows(session_with_roles):
    # Rows written by log_audit (via service mutations) are readable by
    # list_audit_logs — verifies the viewer reads the same AuditLog table the
    # services write to, and org-scoping holds for org_admin.
    db = session_with_roles
    o1 = _org(db, "o1")
    cur = _current(db, o1)
    target = _user(db, "t@x.com", o1)
    svc.set_user_status(db, current=cur, user_id=target.id, status=UserStatus.disabled)
    db.flush()
    out = svc.list_audit_logs(db, current=cur, action=AuditAction.permission_change)
    assert any(i.entity_id == str(target.id) for i in out.items)
    assert all(i.organization_id == o1.id for i in out.items)
