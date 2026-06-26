"""Admin backoffice router (FR-ADMIN-03..07).

Thin delegation to ``app.services.admin`` — handlers own NO business logic.
GETs do not commit; mutations (POST/PUT/PATCH/DELETE) commit after the service
succeeds and roll back on ``AdminError``. ``_exc`` maps the service exception
hierarchy to HTTP statuses: NotFound -> 404, ConflictError -> 409,
ValidationError -> 422 (mirrors taxonomy_admin / practice / exam).

Permission gating follows the design spec's per-endpoint mapping:
- users + classes (FR-ADMIN-03): ``admin:manage_users``
- CAT params (FR-ADMIN-04): ``admin:manage_taxonomy``
- quality queue (FR-ADMIN-05): ``question:publish``
- audit viewer (FR-ADMIN-06): ``admin:view_audit``
- reports (FR-ADMIN-07): ``admin:view_reports``
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser, require_permission
from app.db.session import get_session
from app.models.enums import AuditAction, QuestionFeedbackType
from app.schemas.admin import (
    CatParamsIn,
    CatParamsVersionOut,
    ClassIn,
    ClassOut,
    ClassMemberOut,
    FeedbackOut,
    FeedbackResolveIn,
    LowAccuracyQuestionOut,
    MissingExplanationQuestionOut,
    PaginatedAudit,
    QualityDashboardOut,
    ReportSummaryOut,
    UserOut,
    UserRolesIn,
    UserStatusIn,
)
from app.services import admin as svc

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _exc(e: Exception) -> HTTPException:
    """Map an admin-service exception to an HTTPException."""
    if isinstance(e, svc.NotFound):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, svc.ConflictError):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, svc.ValidationError):
        return HTTPException(status_code=422, detail=str(e))
    raise e


class _ClassMemberIn(BaseModel):
    """Request body for adding a class member (POST /classes/{id}/members).

    Defined inline rather than in schemas/admin.py to keep this task's diff
    to the router + main + tests only, per the task brief.
    """

    user_id: uuid.UUID


# ---- FR-ADMIN-03: users ----

@router.get("/users")
def list_users(
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_users")),
):
    items, total = svc.list_users(
        session, current=current, search=search, limit=limit, offset=offset
    )
    return {"items": items, "total": total}


@router.get("/users/{user_id}", response_model=UserOut)
def get_user_detail(
    user_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_users")),
):
    try:
        return svc.get_user(session, current=current, user_id=user_id)
    except svc.AdminError as e:
        raise _exc(e)


@router.patch("/users/{user_id}/status", response_model=UserOut)
def update_user_status(
    user_id: uuid.UUID,
    payload: UserStatusIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_users")),
):
    try:
        out = svc.set_user_status(
            session, current=current, user_id=user_id, status=payload.status
        )
        session.commit()
        return out
    except svc.AdminError as e:
        session.rollback()
        raise _exc(e)


@router.put("/users/{user_id}/roles", response_model=UserOut)
def set_user_roles(
    user_id: uuid.UUID,
    payload: UserRolesIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_users")),
):
    try:
        out = svc.set_user_roles(
            session, current=current, user_id=user_id, role_names=payload.role_names
        )
        session.commit()
        return out
    except svc.AdminError as e:
        session.rollback()
        raise _exc(e)


# ---- FR-ADMIN-03: classes ----

@router.get("/classes")
def list_classes(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_users")),
):
    items, total = svc.list_classes(
        session, current=current, limit=limit, offset=offset
    )
    return {"items": items, "total": total}


@router.post("/classes", response_model=ClassOut, status_code=200)
def create_class(
    payload: ClassIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_users")),
):
    try:
        out = svc.create_class(session, current=current, payload=payload)
        session.commit()
        return out
    except svc.AdminError as e:
        session.rollback()
        raise _exc(e)


@router.get("/classes/{class_id}", response_model=ClassOut)
def get_class_detail(
    class_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_users")),
):
    try:
        return svc.get_class(session, current=current, class_id=class_id)
    except svc.AdminError as e:
        raise _exc(e)


@router.patch("/classes/{class_id}", response_model=ClassOut)
def update_class(
    class_id: uuid.UUID,
    payload: ClassIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_users")),
):
    try:
        out = svc.update_class(
            session, current=current, class_id=class_id, payload=payload
        )
        session.commit()
        return out
    except svc.AdminError as e:
        session.rollback()
        raise _exc(e)


@router.delete("/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(
    class_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_users")),
):
    try:
        svc.delete_class(session, current=current, class_id=class_id)
        session.commit()
    except svc.AdminError as e:
        session.rollback()
        raise _exc(e)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/classes/{class_id}/members", response_model=list[ClassMemberOut])
def list_class_members(
    class_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_users")),
):
    try:
        return svc.list_class_members(session, current=current, class_id=class_id)
    except svc.AdminError as e:
        raise _exc(e)


@router.post("/classes/{class_id}/members", status_code=status.HTTP_204_NO_CONTENT)
def add_class_member(
    class_id: uuid.UUID,
    payload: _ClassMemberIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_users")),
):
    try:
        svc.add_class_member(
            session, current=current, class_id=class_id, user_id=payload.user_id
        )
        session.commit()
    except svc.AdminError as e:
        session.rollback()
        raise _exc(e)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/classes/{class_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_class_member(
    class_id: uuid.UUID,
    user_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_users")),
):
    try:
        svc.remove_class_member(
            session, current=current, class_id=class_id, user_id=user_id
        )
        session.commit()
    except svc.AdminError as e:
        session.rollback()
        raise _exc(e)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- FR-ADMIN-04: CAT params ----

@router.get("/cat-params", response_model=list[CatParamsVersionOut])
def list_cat_params(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    # list_cat_params is a pure read (no current-user scoping needed — CAT
    # params are GLOBAL exam config), but the route still requires
    # admin:manage_taxonomy so only privileged admins can list versions.
    return svc.list_cat_params(session)


@router.post("/cat-params", response_model=CatParamsVersionOut)
def create_cat_params(
    payload: CatParamsIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        out = svc.create_cat_params(session, current=current, payload=payload)
        session.commit()
        return out
    except svc.AdminError as e:
        session.rollback()
        raise _exc(e)


@router.put("/cat-params/{version_id}/current", response_model=CatParamsVersionOut)
def set_current_cat_params(
    version_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        out = svc.set_current_cat_params(
            session, current=current, version_id=version_id
        )
        session.commit()
        return out
    except svc.AdminError as e:
        session.rollback()
        raise _exc(e)


# ---- FR-ADMIN-05: content quality ----

@router.get("/quality/dashboard", response_model=QualityDashboardOut)
def quality_dashboard(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:publish")),
):
    try:
        return svc.quality_dashboard(session, current=current)
    except svc.AdminError as e:
        raise _exc(e)


@router.get("/quality/feedback")
def list_quality_feedback(
    feedback_type: QuestionFeedbackType | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:publish")),
):
    try:
        items, total = svc.list_open_feedback(
            session, current=current, feedback_type=feedback_type,
            limit=limit, offset=offset,
        )
    except svc.AdminError as e:
        raise _exc(e)
    return {"items": items, "total": total}


@router.patch("/quality/feedback/{feedback_id}", response_model=FeedbackOut)
def resolve_quality_feedback(
    feedback_id: uuid.UUID,
    payload: FeedbackResolveIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:publish")),
):
    try:
        out = svc.resolve_feedback(
            session, current=current, feedback_id=feedback_id, payload=payload
        )
        session.commit()
        return out
    except svc.AdminError as e:
        session.rollback()
        raise _exc(e)


@router.get("/quality/low-accuracy", response_model=list[LowAccuracyQuestionOut])
def list_low_accuracy(
    limit: int = Query(10, ge=1, le=200),
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:publish")),
):
    try:
        return svc.list_low_accuracy_questions(
            session, current=current, limit=limit
        )
    except svc.AdminError as e:
        raise _exc(e)


@router.get(
    "/quality/missing-explanations",
    response_model=list[MissingExplanationQuestionOut],
)
def list_missing_explanations(
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:publish")),
):
    try:
        return svc.list_missing_explanation_questions(
            session, current=current, limit=limit
        )
    except svc.AdminError as e:
        raise _exc(e)


# ---- FR-ADMIN-06: audit log viewer ----

@router.get("/audit-logs", response_model=PaginatedAudit)
def list_audit_logs(
    action: AuditAction | None = None,
    actor_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    org_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:view_audit")),
):
    try:
        return svc.list_audit_logs(
            session, current=current, action=action, actor_id=actor_id,
            entity_type=entity_type, since=since, until=until, org_id=org_id,
            limit=limit, offset=offset,
        )
    except svc.AdminError as e:
        raise _exc(e)


# ---- FR-ADMIN-07: operational reports ----

@router.get("/reports/summary", response_model=ReportSummaryOut)
def report_summary(
    org_id: uuid.UUID | None = None,
    window_days: int = Query(30),
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:view_reports")),
):
    try:
        return svc.report_summary(
            session, current=current, org_id=org_id, window_days=window_days
        )
    except svc.AdminError as e:
        raise _exc(e)


# ---- FR-LANG: admin language-coverage alias ----

@router.get("/questions/language-coverage")
def admin_language_coverage(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:view_reports")),
):
    """FR-LANG coverage report (admin alias of GET /api/questions/language-
    coverage): count in-scope questions by en-only / zh-only / both / neither.
    Org-scoped for org_admin, global for system_admin."""
    return svc.language_coverage(session, current=current)
