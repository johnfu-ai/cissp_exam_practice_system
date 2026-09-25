"""Wrong-book (错题集) HTTP API — PRD v1.4 FR-WRONG."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dependencies import CurrentUser, require_permission
from app.schemas.practice import SessionOut
from app.services import wrong_book as svc
from app.services.errors import ValidationError

router = APIRouter(prefix="/api/wrong-book", tags=["wrong-book"])


@router.get("")
def get_wrong_book(
    current: CurrentUser = Depends(require_permission("practice:read")),
    session: Session = Depends(get_session),
    tab: str = "wrong",
    paper_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """FR-WRONG-02/03: tab=wrong|bookmarked|flagged with an optional paper
    filter. Items carry the question content so clients render inline."""
    try:
        items, total = svc.list_wrong_book(
            session, user_id=current.user.id, org_id=current.org_id, tab=tab,
            paper_id=paper_id, limit=limit, offset=offset,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"items": items, "total": total}


class WrongBookPracticeIn(BaseModel):
    paper_id: uuid.UUID | None = None
    count: int = Field(default=50, ge=1, le=200)
    language_mode: str | None = None


@router.post("/practice", response_model=SessionOut)
def create_wrong_book_practice(
    payload: WrongBookPracticeIn,
    current: CurrentUser = Depends(require_permission("practice:read")),
    session: Session = Depends(get_session),
):
    """FR-WRONG-03: launch a practice session over the current wrong tab
    (optionally filtered to one paper)."""
    from app.models.enums import AuditAction, PracticeSessionStatus
    from app.models.practice import PracticeSession
    from app.services.audit import log_audit
    from app.services.errors import ValidationError as SvcValidationError
    from app.services.i18n import resolve_mode

    try:
        qids = svc.wrong_book_question_ids(
            session, user_id=current.user.id, org_id=current.org_id,
            paper_id=payload.paper_id,
        )
    except SvcValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not qids:
        raise HTTPException(status_code=422, detail="wrong book is empty")
    mode = resolve_mode(session, current.user.id, payload.language_mode)
    qids = qids[: payload.count]
    ps = PracticeSession(
        user_id=current.user.id,
        organization_id=current.org_id,
        status=PracticeSessionStatus.in_progress,
        total_questions=len(qids),
        config={
            "subset": "wrong",
            "order_mode": "sequential",
            "count": len(qids),
            "language_mode": mode,
            "shuffle_options": False,
            "question_ids": [str(q) for q in qids],
            **({"paper_id": str(payload.paper_id)} if payload.paper_id else {}),
        },
    )
    session.add(ps)
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=current.user.id,
        organization_id=current.org_id, entity_type="practice_session",
        entity_id=str(ps.id),
        details={"subset": "wrong", "paper_id": str(payload.paper_id or "")},
    )
    return ps
