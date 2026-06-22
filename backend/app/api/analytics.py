"""Analytics HTTP API — personal learning analytics (sub-project H1).

Thin router over ``app.services.analytics``. All 7 endpoints are GETs gated
by ``require_permission("practice:read")`` and do NOT commit (read-only).
``window_days`` for /trend must be 30 or 90 (else 422). The /domains,
/recommendation, and /report endpoints look up the current ExamBlueprint via
``svc._current_blueprint_or_none`` (None -> graceful empty/None structures).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dependencies import CurrentUser, require_permission
from app.services import analytics as svc

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# Allowed trend windows (PRD spec — must match the service's _TREND_WINDOWS).
_TREND_WINDOWS = (30, 90)


@router.get("/dashboard")
def get_dashboard(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    return svc.dashboard(session, user_id=current.user.id)


@router.get("/domains")
def get_domains(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    bp = svc._current_blueprint_or_none(session)
    return svc.domain_mastery(session, user_id=current.user.id, blueprint=bp)


@router.get("/trend")
def get_trend(
    window_days: int = Query(30),
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    if window_days not in _TREND_WINDOWS:
        raise HTTPException(
            status_code=422, detail="window_days must be 30 or 90"
        )
    return svc.trend(session, user_id=current.user.id, window_days=window_days)


@router.get("/weak-areas")
def get_weak_areas(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    return svc.weak_areas(session, user_id=current.user.id)


@router.get("/error-types")
def get_error_types(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    return svc.error_type_breakdown(session, user_id=current.user.id)


@router.get("/recommendation")
def get_recommendation(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    bp = svc._current_blueprint_or_none(session)
    return svc.recommendation(session, user_id=current.user.id, blueprint=bp)


@router.get("/report")
def get_report(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    bp = svc._current_blueprint_or_none(session)
    return svc.personal_report(session, user_id=current.user.id, blueprint=bp)
