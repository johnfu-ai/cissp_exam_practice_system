"""Practice session service (sub-project E).

Owns session creation, question delivery, answer judging (from snapshot),
pause/resume, finish/summary, and per-user question state.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.queries import not_deleted
from app.models.enums import (
    AuditAction,
    MasteryLevel,
    PracticeSessionStatus,
    QuestionStatus,
)
from app.models.practice import (
    PracticeAnswer,
    PracticeSession,
    UserQuestionState,
)
from app.models.question import (
    Explanation,
    Question,
    QuestionMapping,
    QuestionOption,
)
from app.schemas.practice import (
    AnswerIn,
    AnswerResultOut,
    QuestionStateIn,
    SessionCreateIn,
    SessionSummaryOut,
)
from app.services.audit import log_audit
from app.services.snapshot import snapshot_question


class ValidationError(ValueError):
    pass


class NotFound(LookupError):
    pass


class ConflictError(ValueError):
    pass


def _candidate_question_ids(
    session: Session, *, org_id, payload: SessionCreateIn
) -> list[uuid.UUID]:
    stmt = select(Question.id).where(
        Question.organization_id == org_id,
        Question.status == QuestionStatus.published,
        not_deleted(Question),
    )
    if payload.domain_id is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(
                QuestionMapping.domain_id == payload.domain_id
            )
        ))
    if payload.book_id is not None:
        from app.models.question import Chapter

        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(
                QuestionMapping.chapter_id.in_(
                    select(Chapter.id).where(Chapter.book_id == payload.book_id)
                )
            )
        ))
    if payload.chapter_ids:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(
                QuestionMapping.chapter_id.in_(payload.chapter_ids)
            )
        ))
    if payload.tag_id is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(
                QuestionMapping.tag_id == payload.tag_id
            )
        ))
    if payload.question_type is not None:
        stmt = stmt.where(Question.question_type == payload.question_type)
    if payload.difficulty is not None:
        stmt = stmt.where(Question.difficulty == payload.difficulty)
    return [row[0] for row in session.execute(stmt).all()]


def _apply_subset(
    session: Session, *, user_id, candidate_ids: list[uuid.UUID], subset: str
) -> list[uuid.UUID]:
    if subset == "all" or not candidate_ids:
        return candidate_ids
    if subset == "unpracticed":
        answered = set(
            session.execute(
                select(PracticeAnswer.question_id).where(
                    PracticeAnswer.user_id == user_id,
                    PracticeAnswer.question_id.in_(candidate_ids),
                )
            ).scalars().all()
        )
        return [q for q in candidate_ids if q not in answered]
    if subset == "wrong":
        rows = session.execute(
            select(PracticeAnswer.question_id).where(
                PracticeAnswer.user_id == user_id,
                PracticeAnswer.question_id.in_(candidate_ids),
                PracticeAnswer.is_correct.is_(False),
            )
        ).scalars().all()
        seen = set(rows)
        return [q for q in candidate_ids if q in seen]
    if subset == "bookmarked":
        rows = session.execute(
            select(UserQuestionState.question_id).where(
                UserQuestionState.user_id == user_id,
                UserQuestionState.is_bookmarked.is_(True),
                UserQuestionState.question_id.in_(candidate_ids),
            )
        ).scalars().all()
        seen = set(rows)
        return [q for q in candidate_ids if q in seen]
    if subset == "needs_review":
        rows = session.execute(
            select(UserQuestionState.question_id).where(
                UserQuestionState.user_id == user_id,
                UserQuestionState.is_flagged_review.is_(True),
                UserQuestionState.question_id.in_(candidate_ids),
            )
        ).scalars().all()
        seen = set(rows)
        return [q for q in candidate_ids if q in seen]
    return candidate_ids


def _order_questions(
    session: Session, *, ids: list[uuid.UUID], order_mode: str
) -> list[uuid.UUID]:
    if not ids:
        return []
    if order_mode == "random":
        return list(session.execute(
            select(Question.id)
            .where(Question.id.in_(ids))
            .order_by(func.random())
        ).scalars().all())
    if order_mode == "easy_to_hard":
        return list(session.execute(
            select(Question.id)
            .where(Question.id.in_(ids))
            .order_by(Question.difficulty.asc().nulls_last(), Question.created_at.asc())
        ).scalars().all())
    # sequential
    return list(session.execute(
        select(Question.id)
        .where(Question.id.in_(ids))
        .order_by(Question.created_at.asc())
    ).scalars().all())


def create_session(
    session: Session, *, org_id, actor_id, payload: SessionCreateIn
) -> PracticeSession:
    candidate_ids = _candidate_question_ids(session, org_id=org_id, payload=payload)
    candidate_ids = _apply_subset(
        session, user_id=actor_id, candidate_ids=candidate_ids, subset=payload.subset
    )
    ordered = _order_questions(
        session, ids=candidate_ids, order_mode=payload.order_mode
    )
    ordered = ordered[: payload.count]
    if not ordered:
        raise ValidationError("no questions match the selected scope")
    ps = PracticeSession(
        user_id=actor_id,
        organization_id=org_id,
        status=PracticeSessionStatus.in_progress,
        total_questions=len(ordered),
        config={
            "subset": payload.subset,
            "order_mode": payload.order_mode,
            "count": payload.count,
            "question_ids": [str(qid) for qid in ordered],
        },
    )
    session.add(ps)
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=actor_id, organization_id=org_id,
        entity_type="practice_session", entity_id=str(ps.id),
        details={"total_questions": len(ordered)},
    )
    return ps
