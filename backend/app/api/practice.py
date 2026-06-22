"""Practice HTTP API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dependencies import CurrentUser, require_permission
from app.schemas.practice import (
    AnswerIn,
    AnswerResultOut,
    QuestionDeliveryOut,
    QuestionStateIn,
    SessionCreateIn,
    SessionOut,
    SessionSummaryOut,
)
from app.services import practice as svc

router = APIRouter(prefix="/api/practice", tags=["practice"])


def _session_out(ps) -> SessionOut:
    return SessionOut(
        id=ps.id, status=ps.status.value, total_questions=ps.total_questions,
        correct_count=ps.correct_count, started_at=ps.started_at,
        ended_at=ps.ended_at, paused_at=ps.paused_at, config=ps.config or {},
    )


@router.post("/sessions", response_model=SessionOut)
def create_session(
    body: SessionCreateIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        ps = svc.create_session(
            session, org_id=current.org_id, actor_id=current.user.id, payload=body
        )
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(ps)
    return _session_out(ps)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session_detail(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        ps = svc._load_session(session, session_id, current.user.id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session not found")
    return _session_out(ps)


@router.get("/sessions/{session_id}/questions/{position}", response_model=QuestionDeliveryOut)
def get_question(
    session_id: uuid.UUID,
    position: int,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        return svc.get_question_at(
            session, session_id=session_id, position=position, user_id=current.user.id
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session not found")
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/sessions/{session_id}/answers", response_model=AnswerResultOut)
def submit_answer(
    session_id: uuid.UUID,
    body: AnswerIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        result = svc.submit_answer(
            session, session_id=session_id, user_id=current.user.id, payload=body
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session or question not found")
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return result


@router.post("/sessions/{session_id}/pause", response_model=SessionOut)
def pause_session(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        ps = svc.pause_session(session, session_id=session_id, user_id=current.user.id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session not found")
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    session.refresh(ps)
    return _session_out(ps)


@router.post("/sessions/{session_id}/resume", response_model=SessionOut)
def resume_session(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        ps = svc.resume_session(session, session_id=session_id, user_id=current.user.id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session not found")
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    session.refresh(ps)
    return _session_out(ps)


@router.post("/sessions/{session_id}/finish", response_model=SessionSummaryOut)
def finish_session(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        summary = svc.finish_session(
            session, session_id=session_id, user_id=current.user.id
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session not found")
    session.commit()
    return summary


@router.get("/sessions/{session_id}/summary", response_model=SessionSummaryOut)
def get_summary(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        return svc.get_summary(session, session_id=session_id, user_id=current.user.id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session not found")


@router.put("/questions/{question_id}/state")
def set_question_state(
    question_id: uuid.UUID,
    body: QuestionStateIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("practice:read")),
):
    try:
        state = svc.set_question_state(
            session, user_id=current.user.id, org_id=current.org_id,
            question_id=question_id, payload=body,
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="question not found")
    session.commit()
    return {
        "is_bookmarked": state.is_bookmarked,
        "is_flagged_review": state.is_flagged_review,
        "is_mastered": state.is_mastered,
        "is_questioned": state.is_questioned,
        "note": state.note,
        "error_type": state.error_type.value if state.error_type else None,
    }
