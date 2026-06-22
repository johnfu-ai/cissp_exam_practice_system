"""Fixed exam HTTP API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dependencies import CurrentUser, require_permission
from app.schemas.exam import (
    ExamAnswerAck,
    ExamAnswerIn,
    ExamCreateIn,
    ExamReportOut,
    ExamSessionOut,
    QuestionDeliveryOut,
    ReviewItemOut,
)
from app.services import exam as svc

router = APIRouter(prefix="/api/exam", tags=["exam"])


_INTERNAL_CONFIG_KEYS = {
    "question_ids", "next_question_id", "seen",
    "domain_targets", "domain_answered", "cat_params",
}


def _session_out(es) -> ExamSessionOut:
    remaining = None
    if es.status.value == "in_progress":
        try:
            from datetime import datetime, timezone
            dl = datetime.fromisoformat(es.config.get("deadline_at"))
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            remaining = max(0, int((dl - datetime.now(timezone.utc)).total_seconds() * 1000))
        except Exception:
            remaining = None
    safe_config = {
        k: v for k, v in (es.config or {}).items()
        if k not in _INTERNAL_CONFIG_KEYS
    }
    return ExamSessionOut(
        id=es.id, status=es.status.value, session_kind=es.session_kind.value,
        total_questions=es.total_questions, correct_count=es.correct_count,
        started_at=es.started_at, ended_at=es.ended_at,
        time_remaining_ms=remaining, config=safe_config,
    )


@router.post("/sessions", response_model=ExamSessionOut)
def create_exam(
    body: ExamCreateIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    try:
        es = svc.create_session(
            session, org_id=current.org_id, actor_id=current.user.id, payload=body
        )
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(es)
    return _session_out(es)


@router.get("/sessions/{session_id}", response_model=ExamSessionOut)
def get_exam_detail(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    try:
        es = svc._load_session(session, session_id, current.user.id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="exam session not found")
    return _session_out(es)


@router.get("/sessions/{session_id}/questions/{position}", response_model=QuestionDeliveryOut)
def get_exam_question(
    session_id: uuid.UUID,
    position: int,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    try:
        return svc.get_question_at(
            session, session_id=session_id, position=position, user_id=current.user.id
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session or question not found")
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/sessions/{session_id}/next", response_model=QuestionDeliveryOut)
def get_exam_next(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    """CAT-only: deliver the adaptively-selected current item."""
    try:
        return svc.get_next_question(
            session, session_id=session_id, user_id=current.user.id
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session or question not found")
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/sessions/{session_id}/answers", response_model=ExamAnswerAck)
def submit_exam_answer(
    session_id: uuid.UUID,
    body: ExamAnswerIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    try:
        ack = svc.submit_answer(
            session, session_id=session_id, user_id=current.user.id, payload=body
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session or question not found")
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return ack


@router.post("/sessions/{session_id}/finish", response_model=ExamReportOut)
def finish_exam(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    try:
        report = svc.finish_session(
            session, session_id=session_id, user_id=current.user.id
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="exam session not found")
    session.commit()
    return report


@router.get("/sessions/{session_id}/report", response_model=ExamReportOut)
def get_exam_report(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    try:
        return svc.get_report(session, session_id=session_id, user_id=current.user.id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="exam session not found")
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/sessions/{session_id}/review", response_model=list[ReviewItemOut])
def get_exam_review(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    try:
        return svc.get_review(session, session_id=session_id, user_id=current.user.id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="exam session not found")
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/history")
def list_exam_history(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    return svc.list_history(session, user_id=current.user.id)
