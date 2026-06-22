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


def _load_session(session: Session, session_id, user_id) -> PracticeSession:
    ps = session.get(PracticeSession, session_id)
    if ps is None or ps.user_id != user_id:
        raise NotFound(f"practice session {session_id} not found")
    return ps


def _options_for(session: Session, question_id) -> list[QuestionOption]:
    return list(
        session.execute(
            select(QuestionOption)
            .where(QuestionOption.question_id == question_id)
            .order_by(QuestionOption.order_index)
        ).scalars().all()
    )


def get_question_at(
    session: Session, *, session_id, position: int, user_id
) -> dict:
    ps = _load_session(session, session_id, user_id)
    qids = ps.config.get("question_ids", [])
    if position < 0 or position >= len(qids):
        raise ValidationError("position out of range")
    question = session.get(Question, uuid.UUID(qids[position]))
    if question is None or question.deleted_at is not None:
        raise NotFound("question no longer available")
    options = _options_for(session, question.id)
    started = ps.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    elapsed_ms = int(
        (datetime.now(timezone.utc) - started).total_seconds() * 1000
    )
    prev = session.execute(
        select(PracticeAnswer).where(
            PracticeAnswer.session_id == ps.id,
            PracticeAnswer.question_id == question.id,
        )
    ).scalars().first()
    return {
        "session_id": str(ps.id),
        "position": position,
        "total": len(qids),
        "question_id": str(question.id),
        "stem": question.stem,
        "question_type": question.question_type.value,
        "options": [
            {
                "id": str(o.id),
                "order_index": o.order_index,
                "content": o.content,
                "content_format": o.content_format.value,
            }
            for o in options
        ],
        "elapsed_ms": elapsed_ms,
        "previous_answer": (
            {
                "selected": prev.user_answer.get("selected"),
                "is_correct": prev.is_correct,
            }
            if prev
            else None
        ),
    }


def _judge(snapshot: dict, selected: list[int]) -> tuple[bool, list[int]]:
    correct_indexes = [
        o["order_index"] for o in snapshot["options"] if o["is_correct"]
    ]
    return (set(selected) == set(correct_indexes)), correct_indexes


def _mapping_out(session: Session, question_id) -> dict:
    m = session.execute(
        select(QuestionMapping).where(QuestionMapping.question_id == question_id)
    ).scalars().first()
    out: dict = {}
    if m is not None:
        out["domain_id"] = str(m.domain_id) if m.domain_id else None
        out["chapter_id"] = str(m.chapter_id) if m.chapter_id else None
        out["knowledge_point_id"] = (
            str(m.knowledge_point_id) if m.knowledge_point_id else None
        )
    return out


def _history_out(
    session: Session, *, user_id, question_id, exclude_session_id
) -> list[dict]:
    rows = session.execute(
        select(PracticeAnswer).where(
            PracticeAnswer.user_id == user_id,
            PracticeAnswer.question_id == question_id,
            PracticeAnswer.session_id != exclude_session_id,
        ).order_by(PracticeAnswer.answered_at.desc())
    ).scalars().all()
    return [
        {
            "session_id": str(r.session_id),
            "is_correct": r.is_correct,
            "answered_at": r.answered_at.isoformat() if r.answered_at else None,
        }
        for r in rows
    ]


def submit_answer(
    session: Session, *, session_id, user_id, payload: AnswerIn
) -> AnswerResultOut:
    ps = _load_session(session, session_id, user_id)
    if ps.status != PracticeSessionStatus.in_progress:
        raise ConflictError("session is not in progress")
    if ps.paused_at is not None:
        raise ConflictError("session is paused")
    qids = ps.config.get("question_ids", [])
    if payload.position < 0 or payload.position >= len(qids):
        raise ValidationError("position out of range")
    question_id = uuid.UUID(qids[payload.position])
    existing = session.execute(
        select(PracticeAnswer).where(
            PracticeAnswer.session_id == ps.id,
            PracticeAnswer.question_id == question_id,
        )
    ).scalars().first()
    if existing is not None:
        raise ConflictError("this question has already been answered in this session")
    question = session.get(Question, question_id)
    if question is None or question.deleted_at is not None:
        raise NotFound("question no longer available")
    options = _options_for(session, question_id)
    snap = snapshot_question(question, options)
    is_correct, correct_indexes = _judge(snap, payload.selected)
    now = datetime.now(timezone.utc)
    started = payload.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    time_spent_ms = max(0, int((now - started).total_seconds() * 1000))
    ans = PracticeAnswer(
        session_id=ps.id,
        user_id=user_id,
        question_id=question_id,
        question_snapshot=snap,
        options_snapshot=snap["options"],
        user_answer={"selected": payload.selected},
        is_correct=is_correct,
        time_spent_ms=time_spent_ms,
    )
    session.add(ans)
    if is_correct:
        ps.correct_count = (ps.correct_count or 0) + 1
    state = session.execute(
        select(UserQuestionState).where(
            UserQuestionState.user_id == user_id,
            UserQuestionState.question_id == question_id,
        )
    ).scalars().first()
    new_level = MasteryLevel.mastered if is_correct else MasteryLevel.learning
    if state is None:
        state = UserQuestionState(
            user_id=user_id, question_id=question_id, mastery_level=new_level
        )
        session.add(state)
    else:
        state.mastery_level = new_level
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=user_id,
        organization_id=ps.organization_id, entity_type="practice_answer",
        entity_id=str(ans.id), details={"is_correct": is_correct},
    )
    explanation = session.execute(
        select(Explanation).where(Explanation.question_id == question_id)
    ).scalars().first()
    return AnswerResultOut(
        is_correct=is_correct,
        correct_indexes=correct_indexes,
        selected_indexes=list(payload.selected),
        correct_rationale=(
            explanation.correct_answer_rationale if explanation else None
        ),
        key_point_summary=explanation.key_point_summary if explanation else None,
        per_option=[
            {
                "order_index": o["order_index"],
                "is_correct": o["is_correct"],
                "explanation": next(
                    (
                        opt.explanation
                        for opt in options
                        if opt.order_index == o["order_index"]
                    ),
                    None,
                ),
            }
            for o in snap["options"]
        ],
        mapping=_mapping_out(session, question_id),
        history=_history_out(
            session, user_id=user_id, question_id=question_id,
            exclude_session_id=ps.id,
        ),
    )
