"""Question bank service: CRUD, lifecycle, revisions, feedback.

Route handlers in ``app/api/questions.py`` delegate here. All queries are
ORM/parameterized. Questions are tenant-scoped (``organization_id``) and
soft-deleted (``not_deleted``). The caller is responsible for committing the
session after a successful mutation.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import AuditAction, QuestionStatus, QuestionType
from app.models.question import (
    Explanation,
    Question,
    QuestionMapping,
    QuestionOption,
    QuestionRevision,
)
from app.schemas.question import (
    ExplanationIn,
    MappingsIn,
    OptionIn,
    QuestionCreateIn,
)
from app.services.audit import log_audit
from app.services.snapshot import snapshot_question


class ValidationError(ValueError):
    """Invalid question data (maps to HTTP 422)."""


def _validate_options(qtype: QuestionType, options: list[OptionIn]) -> None:
    n = len(options)
    correct = [o for o in options if o.is_correct]
    if qtype == QuestionType.true_false:
        if n != 2 or len(correct) != 1:
            raise ValidationError(
                "true_false requires exactly 2 options with exactly 1 correct"
            )
    elif qtype == QuestionType.single_choice:
        if not 2 <= n <= 8:
            raise ValidationError("single_choice requires 2-8 options")
        if len(correct) != 1:
            raise ValidationError("single_choice requires exactly 1 correct option")
    elif qtype == QuestionType.multiple_choice:
        if not 2 <= n <= 8:
            raise ValidationError("multiple_choice requires 2-8 options")
        if len(correct) < 2:
            raise ValidationError("multiple_choice requires at least 2 correct options")
    else:
        # scenario / ordering / drag_drop / hotspot: defer strict validation
        if not 2 <= n <= 8:
            raise ValidationError("question requires 2-8 options")


def _next_revision_number(session: Session, question_id) -> int:
    last = session.execute(
        select(QuestionRevision.revision_number)
        .where(QuestionRevision.question_id == question_id)
        .order_by(QuestionRevision.revision_number.desc())
    ).scalars().first()
    return (last or 0) + 1


def _write_revision(session: Session, question: Question, *, actor_id,
                    change_summary: str | None) -> QuestionRevision:
    options = list(
        session.execute(
            select(QuestionOption)
            .where(QuestionOption.question_id == question.id)
            .order_by(QuestionOption.order_index)
        ).scalars().all()
    )
    rev = QuestionRevision(
        question_id=question.id,
        revision_number=_next_revision_number(session, question.id),
        snapshot=snapshot_question(question, options),
        edited_by_id=actor_id,
        change_summary=change_summary,
    )
    session.add(rev)
    return rev


def _apply_mappings(session: Session, question_id, mappings: MappingsIn) -> None:
    if mappings.domain_id is not None:
        session.add(QuestionMapping(question_id=question_id, domain_id=mappings.domain_id))
    if mappings.chapter_id is not None:
        session.add(QuestionMapping(question_id=question_id, chapter_id=mappings.chapter_id))
    if mappings.knowledge_point_id is not None:
        session.add(QuestionMapping(
            question_id=question_id, knowledge_point_id=mappings.knowledge_point_id
        ))
    for tag_id in mappings.tag_ids:
        session.add(QuestionMapping(question_id=question_id, tag_id=tag_id))


def create_question(session: Session, *, org_id, actor_id,
                    payload: QuestionCreateIn) -> Question:
    if not payload.stem.strip():
        raise ValidationError("stem must not be empty")
    _validate_options(payload.question_type, payload.options)

    q = Question(
        organization_id=org_id,
        question_type=payload.question_type,
        stem=payload.stem,
        stem_format=payload.stem_format,
        difficulty=payload.difficulty,
        language=payload.language,
        status=QuestionStatus.draft,
        source=payload.source,
        license_status=payload.license_status,
        prompt_items=payload.prompt_items,
        version=1,
        created_by_id=actor_id,
        updated_by_id=actor_id,
    )
    session.add(q)
    session.flush()

    for i, opt in enumerate(payload.options):
        session.add(QuestionOption(
            question_id=q.id,
            order_index=opt.order_index if opt.order_index is not None else i,
            content=opt.content,
            content_format=opt.content_format,
            is_correct=opt.is_correct,
            explanation=opt.explanation,
        ))

    if payload.explanation is not None:
        session.add(Explanation(
            question_id=q.id,
            correct_answer_rationale=payload.explanation.correct_answer_rationale,
            key_point_summary=payload.explanation.key_point_summary,
            further_reading=payload.explanation.further_reading,
        ))

    _apply_mappings(session, q.id, payload.mappings)
    _write_revision(session, q, actor_id=actor_id, change_summary="initial creation")

    log_audit(session, action=AuditAction.edit, actor_id=actor_id,
              organization_id=org_id, entity_type="question", entity_id=str(q.id),
              details={"action": "create"})
    return q
