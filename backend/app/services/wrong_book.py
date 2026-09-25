"""Persistent wrong-book service (PRD v1.4 FR-WRONG).

`UserQuestionState.wrong_count` / `last_wrong_at` accumulate every judged
incorrect outcome across practice, exam, and paper sessions. This module owns:

* ``record_outcome`` — the single entry point every judging path calls
  (practice submit, exam lazy judge at finish, essay self-assessment).
* ``list_wrong_book`` — the three-tab listing (wrong / bookmarked / flagged)
  with per-item question content and owning-paper names.
* ``create_wrong_book_practice`` — re-practice launcher (subset=wrong with an
  optional paper filter).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.queries import not_deleted
from app.models.enums import MasteryLevel, PaperStatus
from app.models.paper import Paper, PaperQuestion
from app.models.practice import UserQuestionState
from app.models.question import Question, QuestionTranslation
from app.services.errors import NotFound, ValidationError


def record_outcome(
    session: Session, *, user_id, question_id, is_correct: bool | None
) -> UserQuestionState:
    """Apply a judged outcome to the persistent wrong book.

    * incorrect -> wrong_count += 1, last_wrong_at = now, mastery learning
    * correct   -> mastery promoted to mastered (cumulative count untouched)
    * None (essay not yet self-assessed) -> no-op

    Creates the state row when missing. Never called for unanswered items.
    """
    state = session.execute(
        select(UserQuestionState).where(
            UserQuestionState.user_id == user_id,
            UserQuestionState.question_id == question_id,
        )
    ).scalars().first()
    if state is None:
        state = UserQuestionState(user_id=user_id, question_id=question_id)
        session.add(state)
    if is_correct is False:
        state.wrong_count = (state.wrong_count or 0) + 1
        state.last_wrong_at = datetime.now(timezone.utc)
        state.mastery_level = MasteryLevel.learning
        state.is_mastered = False
    elif is_correct is True:
        state.mastery_level = MasteryLevel.mastered
    session.flush()
    return state


def _papers_for_questions(session: Session, question_ids) -> dict:
    """Map question_id -> [paper names] (published papers only)."""
    if not question_ids:
        return {}
    rows = session.execute(
        select(PaperQuestion.question_id, Paper.name)
        .join(Paper, Paper.id == PaperQuestion.paper_id)
        .where(
            PaperQuestion.question_id.in_(question_ids),
            not_deleted(Paper),
            Paper.status == PaperStatus.published,
        )
    ).all()
    out: dict = {}
    for qid, name in rows:
        out.setdefault(qid, []).append(name)
    return out


def list_wrong_book(
    session: Session,
    *,
    user_id,
    org_id,
    tab: str = "wrong",
    paper_id=None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return (items, total) for one wrong-book tab.

    tab=wrong: wrong_count > 0 AND not mastered (FR-WRONG-02)
    tab=bookmarked / tab=flagged: the respective state flags.
    """
    if tab not in ("wrong", "bookmarked", "flagged"):
        raise ValidationError("tab must be one of wrong|bookmarked|flagged")

    stmt = (
        select(UserQuestionState, Question)
        .join(Question, Question.id == UserQuestionState.question_id)
        .where(
            UserQuestionState.user_id == user_id,
            Question.organization_id == org_id,
            not_deleted(Question),
        )
    )
    if tab == "wrong":
        stmt = stmt.where(
            UserQuestionState.wrong_count > 0,
            UserQuestionState.is_mastered.is_(False),
        )
    elif tab == "bookmarked":
        stmt = stmt.where(UserQuestionState.is_bookmarked.is_(True))
    else:
        stmt = stmt.where(UserQuestionState.is_flagged_review.is_(True))
    if paper_id is not None:
        stmt = stmt.where(
            UserQuestionState.question_id.in_(
                select(PaperQuestion.question_id).where(
                    PaperQuestion.paper_id == paper_id
                )
            )
        )

    from sqlalchemy import func

    total = session.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()

    order_col = (
        UserQuestionState.last_wrong_at.desc()
        if tab == "wrong"
        else UserQuestionState.updated_at.desc()
    )
    rows = list(
        session.execute(
            stmt.order_by(order_col).limit(limit).offset(offset)
        ).all()
    )

    qids = [q.id for _, q in rows]
    trans_by_q: dict = {}
    for t in session.execute(
        select(QuestionTranslation).where(QuestionTranslation.question_id.in_(qids))
    ).scalars().all():
        trans_by_q.setdefault(t.question_id, []).append(t)
    papers_by_q = _papers_for_questions(session, qids)

    items = []
    for state, q in rows:
        translations = trans_by_q.get(q.id, [])

        def loc(field: str) -> dict:
            return {
                "en": next(
                    (getattr(t, field) for t in translations if t.language == "en"),
                    None,
                ),
                "zh": next(
                    (getattr(t, field) for t in translations if t.language == "zh"),
                    None,
                ),
            }

        options = []
        correct_indexes = []
        for t in sorted(translations, key=lambda x: x.language):
            for o in (t.options or []):
                if any(x["order_index"] == o["order_index"] for x in options):
                    continue
                cell = {
                    "order_index": o["order_index"],
                    "content": {"en": None, "zh": None},
                    "explanation": {"en": None, "zh": None},
                }
                options.append(cell)
        # canonical correctness comes from the option rows
        from app.models.question import QuestionOption

        opt_rows = session.execute(
            select(QuestionOption)
            .where(QuestionOption.question_id == q.id)
            .order_by(QuestionOption.order_index)
        ).scalars().all()
        correct_indexes = [o.order_index for o in opt_rows if o.is_correct]
        for t in translations:
            for o in (t.options or []):
                for cell in options:
                    if cell["order_index"] == o["order_index"]:
                        cell["content"][t.language] = o.get("content")
                        cell["explanation"][t.language] = o.get("explanation")

        items.append({
            "question_id": str(q.id),
            "question_type": q.question_type.value,
            "stem": loc("stem"),
            "options": sorted(options, key=lambda x: x["order_index"]),
            "correct_indexes": correct_indexes,
            "rationale": loc("correct_answer_rationale"),
            "reference_answer": loc("reference_answer"),
            "wrong_count": state.wrong_count,
            "last_wrong_at": (
                state.last_wrong_at.isoformat() if state.last_wrong_at else None
            ),
            "is_mastered": state.is_mastered,
            "is_bookmarked": state.is_bookmarked,
            "is_flagged_review": state.is_flagged_review,
            "mastery_level": (
                state.mastery_level.value
                if hasattr(state.mastery_level, "value")
                else state.mastery_level
            ),
            "papers": papers_by_q.get(q.id, []),
        })
    return items, total


def wrong_book_question_ids(
    session: Session, *, user_id, org_id, paper_id=None
) -> list[uuid.UUID]:
    """Question ids currently in the wrong tab (wrong_count>0, not mastered)."""
    stmt = (
        select(UserQuestionState.question_id)
        .join(Question, Question.id == UserQuestionState.question_id)
        .where(
            UserQuestionState.user_id == user_id,
            UserQuestionState.wrong_count > 0,
            UserQuestionState.is_mastered.is_(False),
            Question.organization_id == org_id,
            not_deleted(Question),
        )
    )
    if paper_id is not None:
        stmt = stmt.where(
            UserQuestionState.question_id.in_(
                select(PaperQuestion.question_id).where(
                    PaperQuestion.paper_id == paper_id
                )
            )
        )
    return list(session.execute(stmt).scalars().all())
