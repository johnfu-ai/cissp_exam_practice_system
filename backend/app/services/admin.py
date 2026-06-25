"""Admin backoffice service (FR-ADMIN-03..07).

All queries are org-scoped for org_admin (current.org_id) and global for
system_admin (None scope). Out-of-scope targets raise NotFound (not 403) to
avoid leaking existence. Mutations write AuditLog via log_audit (flush only;
caller commits).

This module is built up across tasks 4-8 of sub-project H2. Task 4 adds the
exception hierarchy, the org-scoping helper, and the user-management +
class-management functions (FR-ADMIN-03). Later tasks append CAT-params,
quality, audit, and reports functions to this same file.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Integer, func, or_, select
from sqlalchemy.orm import Session

from app.db.queries import not_deleted
from app.dependencies import CurrentUser
from app.models.admin import AuditLog, CatParamsVersion
from app.models.auth import (
    Class,
    ClassMembership,
    OrganizationMembership,
    Role,
    RoleName,
    User,
)
from app.models.enums import AuditAction, UserStatus
from app.models.exam import ExamAnswer, ExamSession
from app.models.practice import PracticeAnswer, PracticeSession
from app.models.question import (
    Question,
    QuestionFeedback,
    QuestionFeedbackStatus as _QFStatus,
    QuestionFeedbackType,
    QuestionStatus,
    QuestionTranslation,
)
from app.schemas.admin import (
    AuditLogOut,
    CatParamsIn,
    CatParamsVersionOut,
    ClassIn,
    ClassMemberOut,
    ClassOut,
    FeedbackOut,
    FeedbackResolveIn,
    LowAccuracyQuestionOut,
    MissingExplanationQuestionOut,
    PaginatedAudit,
    QualityDashboardOut,
    ReportSummaryOut,
    UserOut,
)
from app.services.audit import log_audit


class AdminError(Exception):
    """Base for all admin-service errors. The router (Task 9) catches this one
    base and maps subclasses to HTTP statuses (422/404/409)."""


class ValidationError(AdminError):
    pass


class NotFound(AdminError):
    pass


class ConflictError(AdminError):
    pass


_SYSTEM_ADMIN = RoleName.system_admin.value


def _admin_org_scope(current: CurrentUser) -> uuid.UUID | None:
    """None for system_admin (global); org_id for everyone else."""
    if _SYSTEM_ADMIN in current.roles:
        return None
    return current.org_id


def _user_out(session: Session, user: User, org_id: uuid.UUID) -> UserOut:
    role_names = [
        r.value
        for r in session.execute(
            select(Role.name)
            .join(OrganizationMembership, OrganizationMembership.role_id == Role.id)
            .where(OrganizationMembership.user_id == user.id,
                   OrganizationMembership.organization_id == org_id)
        ).scalars()
    ]
    return UserOut(
        id=user.id, email=user.email, display_name=user.display_name,
        status=user.status.value, default_organization_id=user.default_organization_id,
        roles=role_names,
    )


def _resolve_scope_org(current: CurrentUser, user: User) -> uuid.UUID:
    """Org to use for role listing: admin scope (org_admin) or user's default org (system_admin)."""
    scope = _admin_org_scope(current)
    return scope if scope is not None else (user.default_organization_id or current.org_id)


# ---- FR-ADMIN-03: users ----

def list_users(session, *, current, search=None, limit=50, offset=0):
    scope = _admin_org_scope(current)
    filters = []
    if scope is not None:
        filters.append(OrganizationMembership.organization_id == scope)
    if search:
        filters.append(or_(User.email.ilike(f"%{search}%"),
                           User.display_name.ilike(f"%{search}%")))
    # count DISTINCT users so a user with N roles in the same org counts once,
    # matching the deduped `rows` query below (which uses .scalars().unique()).
    count_q = (select(func.count(func.distinct(User.id)))
               .select_from(User)
               .join(OrganizationMembership,
                     OrganizationMembership.user_id == User.id))
    for f in filters:
        count_q = count_q.where(f)
    total = session.execute(count_q).scalar_one()
    rows_q = select(User).join(OrganizationMembership,
                               OrganizationMembership.user_id == User.id)
    for f in filters:
        rows_q = rows_q.where(f)
    rows = session.execute(
        rows_q.order_by(User.email).limit(limit).offset(offset)
    ).scalars().unique().all()
    out = [_user_out(session, u, _resolve_scope_org(current, u)) for u in rows]
    return out, total


def get_user(session, *, current, user_id):
    user = session.get(User, user_id)
    if user is None:
        raise NotFound("user not found")
    scope = _admin_org_scope(current)
    if scope is not None:
        # Existence check only (a user may have multiple roles in the same org,
        # i.e. multiple OrganizationMembership rows). Use .first(), not
        # .scalar_one_or_none(), which raises MultipleResultsFound on multi-role
        # users (set_user_roles itself creates such memberships).
        in_org = session.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.organization_id == scope,
            )
        ).first()
        if in_org is None:
            raise NotFound("user not found")
    return _user_out(session, user, _resolve_scope_org(current, user))


def set_user_status(session, *, current, user_id, status: UserStatus):
    user = session.get(User, user_id)
    if user is None:
        raise NotFound("user not found")
    get_user(session, current=current, user_id=user_id)  # scope check -> NotFound
    user.status = status
    session.flush()
    log_audit(session, action=AuditAction.permission_change, actor_id=current.user.id,
              organization_id=current.org_id, entity_type="user", entity_id=str(user_id),
              details={"status": status.value})
    return _user_out(session, user, _resolve_scope_org(current, user))


def set_user_roles(session, *, current, user_id, role_names: list[RoleName]):
    user = session.get(User, user_id)
    if user is None:
        raise NotFound("user not found")
    org_id = _resolve_scope_org(current, user)
    # scope check
    if _admin_org_scope(current) is not None:
        get_user(session, current=current, user_id=user_id)
    role_ids = []
    for name in role_names:
        r = session.execute(select(Role).where(Role.name == name)).scalar_one_or_none()
        if r is None:
            raise ValidationError(f"unknown role {name}")
        role_ids.append(r.id)
    # replace memberships in this org only (select-then-delete, project convention)
    existing = session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == org_id,
        )
    ).scalars().all()
    for m in existing:
        session.delete(m)
    for rid in role_ids:
        session.add(OrganizationMembership(user_id=user_id, organization_id=org_id, role_id=rid))
    session.flush()
    log_audit(session, action=AuditAction.permission_change, actor_id=current.user.id,
              organization_id=org_id, entity_type="user", entity_id=str(user_id),
              details={"roles": [n.value for n in role_names]})
    return _user_out(session, user, org_id)


# ---- FR-ADMIN-03: classes ----

def _class_out(session, cls: Class) -> ClassOut:
    count = session.execute(
        select(func.count()).select_from(
            select(ClassMembership).where(ClassMembership.class_id == cls.id).subquery()
        )
    ).scalar_one()
    return ClassOut(id=cls.id, name=cls.name, description=cls.description,
                    instructor_id=cls.instructor_id, organization_id=cls.organization_id,
                    member_count=count)


def _scoped_class(session, current, class_id) -> Class:
    q = select(Class).where(Class.id == class_id, not_deleted(Class))
    scope = _admin_org_scope(current)
    if scope is not None:
        q = q.where(Class.organization_id == scope)
    cls = session.execute(q).scalar_one_or_none()
    if cls is None:
        raise NotFound("class not found")
    return cls


def list_classes(session, *, current, limit=50, offset=0):
    q = select(Class).where(not_deleted(Class))
    scope = _admin_org_scope(current)
    if scope is not None:
        q = q.where(Class.organization_id == scope)
    total = session.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = session.execute(q.order_by(Class.name).limit(limit).offset(offset)).scalars().all()
    return [_class_out(session, c) for c in rows], total


def create_class(session, *, current, payload: ClassIn) -> ClassOut:
    scope = _admin_org_scope(current) or current.org_id
    cls = Class(organization_id=scope, name=payload.name,
                description=payload.description, instructor_id=payload.instructor_id)
    session.add(cls); session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=current.user.id, organization_id=scope,
              entity_type="class", entity_id=str(cls.id), details={"name": payload.name})
    return _class_out(session, cls)


def get_class(session, *, current, class_id) -> ClassOut:
    return _class_out(session, _scoped_class(session, current, class_id))


def update_class(session, *, current, class_id, payload: ClassIn) -> ClassOut:
    cls = _scoped_class(session, current, class_id)
    cls.name = payload.name
    cls.description = payload.description
    cls.instructor_id = payload.instructor_id
    session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=current.user.id,
              organization_id=cls.organization_id, entity_type="class",
              entity_id=str(cls.id), details={"name": payload.name})
    return _class_out(session, cls)


def delete_class(session, *, current, class_id) -> None:
    cls = _scoped_class(session, current, class_id)
    cls.deleted_at = datetime.now(timezone.utc)
    session.flush()
    log_audit(session, action=AuditAction.archive, actor_id=current.user.id,
              organization_id=cls.organization_id, entity_type="class",
              entity_id=str(cls.id), details={"name": cls.name})


def list_class_members(session, *, current, class_id):
    cls = _scoped_class(session, current, class_id)
    rows = session.execute(
        select(User)
        .join(ClassMembership, ClassMembership.user_id == User.id)
        .where(ClassMembership.class_id == cls.id)
        .order_by(User.email)
    ).scalars().all()
    return [ClassMemberOut(user_id=u.id, email=u.email, display_name=u.display_name)
            for u in rows]


def add_class_member(session, *, current, class_id, user_id) -> None:
    cls = _scoped_class(session, current, class_id)
    # user must be in the class's org
    scope = _admin_org_scope(current)
    org_filter = scope if scope is not None else cls.organization_id
    # Existence check only; a user with multiple roles in the org has multiple
    # matching rows, so use .first() (not .scalar_one_or_none()).
    m = session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == org_filter,
        )
    ).first()
    if m is None:
        raise NotFound("user not found")
    existing = session.execute(
        select(ClassMembership).where(ClassMembership.class_id == cls.id,
                                      ClassMembership.user_id == user_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("already a member")
    session.add(ClassMembership(class_id=cls.id, user_id=user_id)); session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=current.user.id,
              organization_id=cls.organization_id, entity_type="class_member",
              entity_id=str(cls.id), details={"user_id": str(user_id)})


def remove_class_member(session, *, current, class_id, user_id) -> None:
    cls = _scoped_class(session, current, class_id)
    m = session.execute(
        select(ClassMembership).where(ClassMembership.class_id == cls.id,
                                      ClassMembership.user_id == user_id)
    ).scalar_one_or_none()
    if m is None:
        raise NotFound("membership not found")
    session.delete(m); session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=current.user.id,
              organization_id=cls.organization_id, entity_type="class_member",
              entity_id=str(cls.id), details={"removed_user_id": str(user_id)})


# ---- FR-ADMIN-04: CAT params ----
# CatParamsVersion is GLOBAL (organization_id=None on the audit row). Only one
# version may have is_current=True at a time; _unset_current clears the prior
# current before a new one is set. Mutations audit as config_change.

def _cat_out(v: CatParamsVersion) -> CatParamsVersionOut:
    return CatParamsVersionOut(id=v.id, version_label=v.version_label,
                               effective_date=v.effective_date, is_current=v.is_current,
                               params=v.params)


def list_cat_params(session) -> list[CatParamsVersionOut]:
    rows = session.execute(
        select(CatParamsVersion).order_by(CatParamsVersion.effective_date.desc())
    ).scalars().all()
    return [_cat_out(v) for v in rows]


def _unset_current(session) -> None:
    # ORM-level update (not a Core bulk UPDATE) so identity-mapped objects stay
    # consistent with the DB — a Core update().values() would leave in-memory
    # rows stale, breaking the "v1.is_current is False" check right after v2 is
    # created with set_current=True.
    rows = session.execute(
        select(CatParamsVersion).where(CatParamsVersion.is_current.is_(True))
    ).scalars().all()
    for v in rows:
        v.is_current = False


def create_cat_params(session, *, current, payload: CatParamsIn) -> CatParamsVersionOut:
    dup = session.execute(
        select(CatParamsVersion).where(CatParamsVersion.version_label == payload.version_label)
    ).scalar_one_or_none()
    if dup is not None:
        raise ConflictError("version_label already exists")
    if payload.set_current:
        _unset_current(session)
    v = CatParamsVersion(version_label=payload.version_label,
                        effective_date=payload.effective_date,
                        is_current=payload.set_current,
                        params=payload.params.model_dump())
    session.add(v); session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=current.user.id,
              organization_id=None, entity_type="cat_params",
              entity_id=str(v.id), details={"version_label": v.version_label,
                                            "set_current": v.is_current})
    return _cat_out(v)


def set_current_cat_params(session, *, current, version_id) -> CatParamsVersionOut:
    v = session.get(CatParamsVersion, version_id)
    if v is None:
        raise NotFound("cat params version not found")
    _unset_current(session)
    v.is_current = True
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=current.user.id,
              organization_id=None, entity_type="cat_params",
              entity_id=str(v.id), details={"set_current": True})
    return _cat_out(v)


def get_current_cat_params(session) -> CatParamsVersion | None:
    return session.execute(
        select(CatParamsVersion).where(CatParamsVersion.is_current.is_(True))
    ).scalar_one_or_none()


# ---- FR-ADMIN-05: content quality ----
#
# Org-scoped for org_admin (current.org_id), global for system_admin (None
# scope). Out-of-scope targets raise NotFound (not 403) to avoid leaking
# existence. Thresholds: low-accuracy = accuracy < 0.6 AND answered >= 5;
# missing-explanation = published Question with NO QuestionTranslation whose
# correct_answer_rationale is non-empty (no translation row, or all
# translations have empty/whitespace-only rationale) — the bilingual
# translations model superseded the old single-language Explanation table;
# disputed = question has >=1 OPEN suspected_wrong_answer feedback.

_LOW_ACC = 0.6
_LOW_ACC_MIN_ANSWERED = 5


def _q_scope(current):
    return _admin_org_scope(current)  # None for system_admin


def _scoped_questions_q(current):
    q = select(Question).where(not_deleted(Question))
    scope = _q_scope(current)
    if scope is not None:
        q = q.where(Question.organization_id == scope)
    return q


def _stems_for(session, question_ids) -> dict:
    """Return ``{question_id: stem}`` for the given question ids, preferring
    the ``en`` translation, then ``zh``, then any available translation, then
    ``""``. Used to populate ``*.stem`` output fields now that ``Question.stem``
    no longer exists — question content lives in ``QuestionTranslation``."""
    if not question_ids:
        return {}
    rows = session.execute(
        select(
            QuestionTranslation.question_id,
            QuestionTranslation.language,
            QuestionTranslation.stem,
        ).where(QuestionTranslation.question_id.in_(question_ids))
    ).all()
    by_q: dict[uuid.UUID, dict[str, str]] = {}
    for qid, lang, stem in rows:
        by_q.setdefault(qid, {})[lang] = stem
    out: dict[uuid.UUID, str] = {}
    for qid in question_ids:
        langs = by_q.get(qid, {})
        # en preferred, then zh, then any (empty/whitespace stems fall through
        # to the next option since "" is falsy).
        out[qid] = (
            langs.get("en") or langs.get("zh") or next(iter(langs.values()), "")
        )
    return out


def _question_ids_with_rationale(session, question_ids) -> set:
    """Return the subset of ``question_ids`` that have at least one
    ``QuestionTranslation`` whose ``correct_answer_rationale`` is non-empty
    after trimming. Used for the "missing-explanation" (now missing-rationale)
    count — a published question is "missing" if its id is NOT in this set."""
    if not question_ids:
        return set()
    return set(
        session.execute(
            select(QuestionTranslation.question_id).where(
                QuestionTranslation.question_id.in_(question_ids),
                func.trim(QuestionTranslation.correct_answer_rationale) != "",
            )
        ).scalars().all()
    )


def _answer_stats(session, current):
    """Returns (stats, qids): stats is {question_id: (answered, correct)} for
    in-scope questions that have answers; qids is the set of in-scope question
    ids (used by callers that need the full in-scope set, not just those with
    answers)."""
    sq = _scoped_questions_q(current).subquery()
    qids = session.execute(select(sq.c.id)).scalars().all()
    stats: dict[uuid.UUID, tuple[int, int]] = {}
    if not qids:
        return stats, set(qids)
    prac = session.execute(
        select(PracticeAnswer.question_id,
               func.count(),
               func.coalesce(func.sum(PracticeAnswer.is_correct.cast(Integer)), 0))
        .where(PracticeAnswer.question_id.in_(qids))
        .group_by(PracticeAnswer.question_id)
    ).all()
    exam = session.execute(
        select(ExamAnswer.question_id,
               func.count(),
               func.coalesce(func.sum(ExamAnswer.is_correct.cast(Integer)), 0))
        .where(ExamAnswer.question_id.in_(qids))
        .group_by(ExamAnswer.question_id)
    ).all()
    for qid, n, c in list(prac) + list(exam):
        a, cc = stats.get(qid, (0, 0))
        stats[qid] = (a + n, cc + int(c))
    return stats, set(qids)


def quality_dashboard(session, *, current) -> QualityDashboardOut:
    stats, _qids = _answer_stats(session, current)
    scope = _q_scope(current)
    org_filter = [Question.organization_id == scope] if scope is not None else []
    open_fb = session.execute(
        select(func.count(QuestionFeedback.id))
        .join(Question, Question.id == QuestionFeedback.question_id)
        .where(not_deleted(Question), QuestionFeedback.status == _QFStatus.open,
               *org_filter)
    ).scalar_one()
    disputed = session.execute(
        select(func.count(func.distinct(QuestionFeedback.question_id)))
        .join(Question, Question.id == QuestionFeedback.question_id)
        .where(not_deleted(Question), QuestionFeedback.status == _QFStatus.open,
               QuestionFeedback.feedback_type == QuestionFeedbackType.suspected_wrong_answer,
               *org_filter)
    ).scalar_one()
    low = sum(1 for (a, c) in stats.values()
              if a >= _LOW_ACC_MIN_ANSWERED and (c / a if a else 0.0) < _LOW_ACC)
    # published questions with NO QuestionTranslation whose rationale is non-empty
    published_q = session.execute(
        select(Question.id).where(not_deleted(Question), Question.status == QuestionStatus.published,
               *org_filter)
    ).scalars().all()
    with_rationale = _question_ids_with_rationale(session, published_q)
    missing = len(set(published_q) - with_rationale)
    return QualityDashboardOut(open_feedback_count=open_fb, disputed_question_count=disputed,
                               low_accuracy_question_count=low, missing_explanation_count=missing)


def list_open_feedback(session, *, current, feedback_type=None, limit=50, offset=0):
    q = (select(QuestionFeedback).join(Question, Question.id == QuestionFeedback.question_id)
         .where(not_deleted(Question), QuestionFeedback.status == _QFStatus.open))
    scope = _q_scope(current)
    if scope is not None:
        q = q.where(Question.organization_id == scope)
    if feedback_type is not None:
        q = q.where(QuestionFeedback.feedback_type == feedback_type)
    total = session.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = session.execute(q.order_by(QuestionFeedback.created_at.desc())
                           .limit(limit).offset(offset)).scalars().all()
    out = [FeedbackOut(id=f.id, question_id=f.question_id, reporter_id=f.reporter_id,
                       feedback_type=f.feedback_type.value, comment=f.comment,
                       status=f.status.value, created_at=f.created_at) for f in rows]
    return out, total


def resolve_feedback(session, *, current, feedback_id, payload: FeedbackResolveIn) -> FeedbackOut:
    f = session.get(QuestionFeedback, feedback_id)
    if f is None:
        raise NotFound("feedback not found")
    # scope check via the question (soft-deleted questions still resolve via
    # session.get; the binding rule is the org-scope comparison only).
    q = session.get(Question, f.question_id)
    if q is None:
        raise NotFound("feedback not found")
    scope = _q_scope(current)
    if scope is not None and q.organization_id != scope:
        raise NotFound("feedback not found")
    f.status = payload.status
    session.flush()
    log_audit(session, action=AuditAction.edit, actor_id=current.user.id,
              organization_id=q.organization_id, entity_type="feedback",
              entity_id=str(f.id), details={"status": payload.status.value})
    return FeedbackOut(id=f.id, question_id=f.question_id, reporter_id=f.reporter_id,
                       feedback_type=f.feedback_type.value, comment=f.comment,
                       status=f.status.value, created_at=f.created_at)


def list_low_accuracy_questions(session, *, current, limit=10) -> list[LowAccuracyQuestionOut]:
    stats, _qids = _answer_stats(session, current)
    rows = []
    for qid, (a, c) in stats.items():
        if a >= _LOW_ACC_MIN_ANSWERED:
            acc = round(c / a, 4)
            if acc < _LOW_ACC:
                rows.append((qid, a, c, acc))
    rows.sort(key=lambda r: r[3])
    rows = rows[:limit]
    if not rows:
        return []
    stems = _stems_for(session, [r[0] for r in rows])
    return [LowAccuracyQuestionOut(question_id=qid, stem=stems.get(qid, ""), answered=a,
                                   correct=c, accuracy=acc) for qid, a, c, acc in rows]


def list_missing_explanation_questions(session, *, current, limit=50) -> list[MissingExplanationQuestionOut]:
    q = select(Question).where(not_deleted(Question), Question.status == QuestionStatus.published)
    scope = _q_scope(current)
    if scope is not None:
        q = q.where(Question.organization_id == scope)
    pubs = session.execute(q.order_by(Question.created_at.desc()).limit(limit * 2)).scalars().all()
    if not pubs:
        return []
    with_rationale = _question_ids_with_rationale(session, [p.id for p in pubs])
    stems = _stems_for(session, [p.id for p in pubs])
    out = [MissingExplanationQuestionOut(question_id=p.id, stem=stems.get(p.id, ""),
                                         status=p.status.value)
           for p in pubs if p.id not in with_rationale][:limit]
    return out


# ---- FR-ADMIN-06: audit log viewer ----
#
# org_admin sees only AuditLog.organization_id == current.org_id (the org_id
# param must equal their own or be omitted; a different org raises
# ValidationError). system_admin (scope None) sees ALL logs — including
# organization_id=None system-level events (e.g. CAT params config_change) —
# and the org_id param further filters. Supports action / actor_id /
# entity_type / since / until filters plus limit/offset pagination, ordered
# most-recent-first.

def list_audit_logs(session, *, current, action=None, actor_id=None, entity_type=None,
                    since=None, until=None, org_id=None, limit=50, offset=0) -> PaginatedAudit:
    scope = _admin_org_scope(current)
    if scope is not None:
        # org_admin: org_id param different from own is forbidden (param
        # validation, not a target lookup -> ValidationError, not NotFound).
        if org_id is not None and org_id != scope:
            raise ValidationError("cannot target another organization")
        effective_org = scope
    else:
        effective_org = org_id  # None = all orgs (incl. system events) for system_admin
    q = select(AuditLog)
    if effective_org is not None:
        q = q.where(AuditLog.organization_id == effective_org)
    if action is not None:
        q = q.where(AuditLog.action == action)
    if actor_id is not None:
        q = q.where(AuditLog.actor_id == actor_id)
    if entity_type is not None:
        q = q.where(AuditLog.entity_type == entity_type)
    if since is not None:
        q = q.where(AuditLog.occurred_at >= since)
    if until is not None:
        q = q.where(AuditLog.occurred_at <= until)
    total = session.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = session.execute(q.order_by(AuditLog.occurred_at.desc())
                           .limit(limit).offset(offset)).scalars().all()
    items = [AuditLogOut(id=r.id, occurred_at=r.occurred_at, action=r.action.value,
                         actor_id=r.actor_id, organization_id=r.organization_id,
                         entity_type=r.entity_type, entity_id=r.entity_id,
                         details=r.details, ip_address=r.ip_address) for r in rows]
    return PaginatedAudit(items=items, total=total, limit=limit, offset=offset)


# ---- FR-ADMIN-07: operational reports ----
#
# report_summary: window_days ∈ {30, 90} else ValidationError. org_admin is
# scoped to own org (the org_id param must equal own or be omitted, else
# ValidationError); system_admin is global, with the optional org_id param
# filtering the question-bank dimension (published/used/usage%) to that org
# while answer/session stats stay global per the brief's rule. Active users =
# distinct users with ≥1 answer in window. total/correct/accuracy are computed
# over BOTH practice + exam answers in window. Published count is in-scope;
# used = distinct in-scope published questions appearing in ≥1 session's
# config.question_ids (window-agnostic); usage% = used/published*100.
# top_error_questions delegates to list_low_accuracy_questions(limit=10).
#
# NOTE: session config.question_ids are stored as JSON *strings* (see
# practice.py / exam.py: ``[str(q) for q in question_ids]``), so they must be
# normalized to ``uuid.UUID`` before intersecting with ``Question.id`` (UUID) —
# otherwise the set intersection is always empty and usage silently reports 0%.

_REPORT_WINDOWS = (30, 90)


def _scoped_user_ids(session, current):
    """Set of user_ids in the admin's org (org_admin), or None for system_admin
    (all users — no user filtering on answer/session stats)."""
    scope = _admin_org_scope(current)
    if scope is None:
        return None
    rows = session.execute(
        select(OrganizationMembership.user_id).where(
            OrganizationMembership.organization_id == scope
        )
    ).scalars().all()
    return set(rows)


def report_summary(session, *, current, org_id=None, window_days=30) -> ReportSummaryOut:
    if window_days not in _REPORT_WINDOWS:
        raise ValidationError("window_days must be 30 or 90")
    scope = _admin_org_scope(current)
    if scope is not None:
        if org_id is not None and org_id != scope:
            raise ValidationError("cannot target another organization")
        report_org = scope
        scope_str = f"org:{scope}"
    else:
        report_org = org_id
        scope_str = f"org:{org_id}" if org_id is not None else "global"

    user_ids = _scoped_user_ids(session, current)  # None or set
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    # answer stats in window (both practice + exam)
    def _filtered_answers(model):
        q = select(model).where(model.answered_at >= cutoff)
        if user_ids is not None:
            q = q.where(model.user_id.in_(user_ids))
        return session.execute(q).scalars().all()

    prac_ans = _filtered_answers(PracticeAnswer)
    exam_ans = _filtered_answers(ExamAnswer)
    total_answers = len(prac_ans) + len(exam_ans)
    correct_answers = (
        sum(1 for a in prac_ans if a.is_correct)
        + sum(1 for a in exam_ans if a.is_correct)
    )
    accuracy = round(correct_answers / total_answers, 4) if total_answers else 0.0
    active_users = len({a.user_id for a in list(prac_ans) + list(exam_ans)})

    # session counts in window
    def _session_count(model):
        q = select(func.count()).select_from(model).where(model.started_at >= cutoff)
        if user_ids is not None:
            q = q.where(model.user_id.in_(user_ids))
        return session.execute(q).scalar_one()

    practice_session_count = _session_count(PracticeSession)
    exam_session_count = _session_count(ExamSession)

    # question bank usage (in scope)
    qq = select(Question).where(not_deleted(Question), Question.status == QuestionStatus.published)
    if report_org is not None:
        qq = qq.where(Question.organization_id == report_org)
    published = session.execute(qq).scalars().all()
    published_question_count = len(published)
    used_qids = set()
    for model in (PracticeSession, ExamSession):
        sq = select(model)
        if user_ids is not None:
            sq = sq.where(model.user_id.in_(user_ids))
        for s in session.execute(sq).scalars().all():
            raw = (s.config or {}).get("question_ids") or []
            # config stores question_ids as JSON strings; normalize to UUID so
            # the intersection with Question.id (UUID) is non-empty.
            used_qids.update(uuid.UUID(q) if isinstance(q, str) else q for q in raw)
    used_in_scope = {q.id for q in published} & used_qids
    used_question_count = len(used_in_scope)
    question_bank_usage_pct = (
        round(used_question_count / published_question_count * 100, 2)
        if published_question_count else 0.0
    )

    top_error = list_low_accuracy_questions(session, current=current, limit=10)

    return ReportSummaryOut(
        scope=scope_str, window_days=window_days, active_users=active_users,
        practice_session_count=practice_session_count, exam_session_count=exam_session_count,
        total_answers=total_answers, correct_answers=correct_answers, accuracy=accuracy,
        published_question_count=published_question_count, used_question_count=used_question_count,
        question_bank_usage_pct=question_bank_usage_pct, top_error_questions=top_error,
    )


# ---- FR-LANG: admin language-coverage alias ----
#
# Alias of GET /api/questions/language-coverage (T4) under the admin router,
# org-scoped for org_admin (current.org_id) and global for system_admin (None
# scope) via _q_scope — mirroring the other admin question queries — rather
# than hard-scoped to current.org_id like the question-bank original. Returns
# the same {en_only, zh_only, both, neither, total} shape so the admin
# backoffice can surface the same coverage breakdown it already renders.

def language_coverage(session, *, current) -> dict:
    q = select(Question.available_languages).where(not_deleted(Question))
    scope = _q_scope(current)
    if scope is not None:
        q = q.where(Question.organization_id == scope)
    rows = session.execute(q).all()
    en_only = zh_only = both = neither = 0
    for (langs,) in rows:
        s = set(langs or [])
        if {"en", "zh"} <= s:
            both += 1
        elif "en" in s:
            en_only += 1
        elif "zh" in s:
            zh_only += 1
        else:
            neither += 1
    return {
        "en_only": en_only,
        "zh_only": zh_only,
        "both": both,
        "neither": neither,
        "total": en_only + zh_only + both + neither,
    }
