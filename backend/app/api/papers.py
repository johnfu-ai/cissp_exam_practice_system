"""Papers (试卷/题库) HTTP API — PRD v1.4 FR-PAPER + v1.5 FR-PAPER-10..12."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dependencies import CurrentUser, require_permission
from app.services import paper as svc
from app.services.errors import ConflictError, NotFound, ValidationError

router = APIRouter(prefix="/api/papers", tags=["papers"])
banks_router = APIRouter(prefix="/api/banks", tags=["papers"])


class PaperSessionCreateIn(BaseModel):
    mode: Literal["practice", "exam"]
    language_mode: str | None = None


class SwitchModeIn(BaseModel):
    mode: Literal["practice", "exam"]


class HeartbeatIn(BaseModel):
    elapsed_seconds: int = 0


@banks_router.get("")
def list_banks(
    current: CurrentUser = Depends(require_permission("practice:read")),
    session: Session = Depends(get_session),
):
    """FR-PAPER-10: free-practice banks (datasets carrying published
    questions), e.g. OSG v10 alongside the mock-paper papers."""
    return {"items": svc.list_banks(session, org_id=current.org_id)}


@router.get("/sessions/in-progress")
def list_in_progress_sessions(
    current: CurrentUser = Depends(require_permission("practice:read")),
    session: Session = Depends(get_session),
):
    """FR-PAPER-12: the caller's resumable paper/bank sessions."""
    return {"items": svc.list_in_progress(
        session, user_id=current.user.id, org_id=current.org_id,
    )}


@router.get("/sessions/{session_id}/state")
def get_session_state(
    session_id: uuid.UUID,
    current: CurrentUser = Depends(require_permission("practice:read")),
    session: Session = Depends(get_session),
):
    """FR-PAPER-12: resume bundle — answer-sheet state, progress, time."""
    try:
        return svc.session_state(
            session, session_id=session_id, user_id=current.user.id,
            org_id=current.org_id,
        )
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/sessions/{session_id}/switch-mode")
def switch_session_mode(
    session_id: uuid.UUID,
    payload: SwitchModeIn,
    current: CurrentUser = Depends(require_permission("practice:read")),
    session: Session = Depends(get_session),
):
    """FR-PAPER-11: convert an in-progress paper session to the other mode,
    preserving answers, snapshots, and time."""
    try:
        result = svc.switch_mode(
            session, session_id=session_id, user_id=current.user.id,
            org_id=current.org_id, mode=payload.mode,
        )
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return result


@router.post("/sessions/{session_id}/heartbeat")
def heartbeat_paper_session(
    session_id: uuid.UUID,
    payload: HeartbeatIn,
    current: CurrentUser = Depends(require_permission("practice:read")),
    session: Session = Depends(get_session),
):
    """FR-PAPER-12 (v1.7): unified active-time heartbeat — works for paper
    practice, bank practice, AND paper exam sessions (the exam countdown is
    budget − accumulated active time)."""
    try:
        result = svc.heartbeat_session(
            session, session_id=session_id, user_id=current.user.id,
            org_id=current.org_id, elapsed_seconds=payload.elapsed_seconds,
        )
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return result


@router.get("")
def list_papers(
    current: CurrentUser = Depends(require_permission("practice:read")),
    session: Session = Depends(get_session),
    include_unpublished: bool = False,
):
    """FR-PAPER-03: published papers for learners (content managers may pass
    ``include_unpublished`` with question:read)."""
    include = include_unpublished
    if include_unpublished and "question:read" not in current.perms:
        raise HTTPException(status_code=403, detail="question:read required")
    items, total = svc.list_papers(
        session, org_id=current.org_id, user_id=current.user.id,
        include_unpublished=include,
    )
    return {"items": items, "total": total}


@router.get("/{paper_id}")
def get_paper(
    paper_id: uuid.UUID,
    current: CurrentUser = Depends(require_permission("practice:read")),
    session: Session = Depends(get_session),
):
    try:
        detail = svc.get_paper(
            session, paper_id=paper_id, org_id=current.org_id,
            user_id=current.user.id,
        )
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    return detail


@router.post("/{paper_id}/sessions")
def create_paper_session(
    paper_id: uuid.UUID,
    payload: PaperSessionCreateIn,
    current: CurrentUser = Depends(require_permission("practice:read")),
    session: Session = Depends(get_session),
):
    """FR-PAPER-04: one-click practice/exam session over the paper's fixed
    question order. Practice sessions continue via the practice API; exam
    sessions via the exam API."""
    try:
        result = svc.create_paper_session(
            session, paper_id=paper_id, org_id=current.org_id,
            actor_id=current.user.id, mode=payload.mode,
            language_mode=payload.language_mode,
        )
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    from app.models.exam import ExamSession

    if isinstance(result, ExamSession):
        from app.api.exam import _session_out

        return _session_out(result)
    from app.schemas.practice import SessionOut

    return SessionOut(
        id=result.id,
        status=result.status.value,
        total_questions=result.total_questions,
        correct_count=result.correct_count or 0,
        started_at=result.started_at,
        ended_at=result.ended_at,
        paused_at=result.paused_at,
        config=result.config or {},
    )


@router.get("/{paper_id}/sessions")
def list_paper_sessions(
    paper_id: uuid.UUID,
    current: CurrentUser = Depends(require_permission("practice:read")),
    session: Session = Depends(get_session),
):
    try:
        items = svc.list_paper_sessions(
            session, paper_id=paper_id, user_id=current.user.id,
            org_id=current.org_id,
        )
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"items": items}
