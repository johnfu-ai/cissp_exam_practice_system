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

from app.db.queries import not_deleted
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
    QuestionUpdateIn,
)
from app.services.audit import log_audit
from app.services.snapshot import snapshot_question


class ValidationError(ValueError):
    """Invalid question data (maps to HTTP 422)."""


class NotFound(LookupError):
    """Question does not exist or is soft-deleted (maps to HTTP 404)."""


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


def get_question(session: Session, question_id) -> Question:
    """Return a live question by id. Raises ``NotFound`` if missing or soft-deleted."""
    q = session.get(Question, question_id)
    if q is None or q.deleted_at is not None:
        raise NotFound(f"question {question_id} not found")
    return q


def list_questions(
    session: Session,
    *,
    org_id,
    page: int = 1,
    size: int = 20,
    filters: dict | None = None,
) -> tuple[list[Question], int]:
    """Tenant-scoped, paginated list of live questions.

    ``filters`` may contain any of: status, question_type, language, difficulty,
    search (stem ILIKE), domain_id, chapter_id, knowledge_point_id, tag_id.
    Returns (items, total).
    """
    from sqlalchemy import func

    filters = filters or {}
    stmt = select(Question).where(Question.organization_id == org_id, not_deleted(Question))
    if (st := filters.get("status")) is not None:
        stmt = stmt.where(Question.status == st)
    if (qt := filters.get("question_type")) is not None:
        stmt = stmt.where(Question.question_type == qt)
    if (lang := filters.get("language")) is not None:
        stmt = stmt.where(Question.language == lang)
    if (diff := filters.get("difficulty")) is not None:
        stmt = stmt.where(Question.difficulty == diff)
    if (search := filters.get("search")) is not None:
        stmt = stmt.where(Question.stem.ilike(f"%{search}%"))
    if (domain_id := filters.get("domain_id")) is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(QuestionMapping.domain_id == domain_id)
        ))
    if (chapter_id := filters.get("chapter_id")) is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(QuestionMapping.chapter_id == chapter_id)
        ))
    if (knowledge_point_id := filters.get("knowledge_point_id")) is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(
                QuestionMapping.knowledge_point_id == knowledge_point_id
            )
        ))
    if (tag_id := filters.get("tag_id")) is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(QuestionMapping.tag_id == tag_id)
        ))

    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    page = max(page, 1)
    size = min(max(size, 1), 100)
    items = list(
        session.execute(
            stmt.order_by(Question.created_at.desc()).offset((page - 1) * size).limit(size)
        ).scalars().all()
    )
    return items, total


def _delete_rows(session: Session, model, question_id) -> None:
    rows = list(
        session.execute(select(model).where(model.question_id == question_id)).scalars().all()
    )
    for r in rows:
        session.delete(r)


def update_question(session: Session, *, question_id, actor_id,
                    payload: QuestionUpdateIn) -> Question:
    """Partial update. Writes a pre-edit revision snapshot, bumps version, and
    revalidates options when supplied. A no-op payload (nothing set) does not
    bump the version.
    """
    q = get_question(session, question_id)
    data = payload.model_dump(exclude_unset=True)
    changed = bool(data)

    if "options" in data:
        opts = data["options"]  # list of dicts
        opt_objs = [OptionIn(**o) for o in opts]
        qtype = data.get("question_type", q.question_type)
        _validate_options(qtype, opt_objs)

    # capture pre-edit snapshot BEFORE mutating (revision records the prior state)
    if changed:
        _write_revision(session, q, actor_id=actor_id, change_summary="update")

    if "stem" in data:
        if not data["stem"].strip():
            raise ValidationError("stem must not be empty")
        q.stem = data["stem"]
    if "stem_format" in data:
        q.stem_format = data["stem_format"]
    if "question_type" in data:
        q.question_type = data["question_type"]
    if "difficulty" in data:
        q.difficulty = data["difficulty"]
    if "language" in data:
        q.language = data["language"]
    if "source" in data:
        q.source = data["source"]
    if "license_status" in data:
        q.license_status = data["license_status"]
    if "prompt_items" in data:
        q.prompt_items = data["prompt_items"]
    if "options" in data:
        _delete_rows(session, QuestionOption, q.id)
        for i, opt in enumerate(opt_objs):
            session.add(QuestionOption(
                question_id=q.id,
                order_index=opt.order_index if opt.order_index is not None else i,
                content=opt.content, content_format=opt.content_format,
                is_correct=opt.is_correct, explanation=opt.explanation,
            ))
    if "explanation" in data:
        _delete_rows(session, Explanation, q.id)
        if data["explanation"] is not None:
            ex = ExplanationIn(**data["explanation"])
            session.add(Explanation(
                question_id=q.id, correct_answer_rationale=ex.correct_answer_rationale,
                key_point_summary=ex.key_point_summary, further_reading=ex.further_reading,
            ))
    if "mappings" in data:
        _delete_rows(session, QuestionMapping, q.id)
        _apply_mappings(session, q.id, MappingsIn(**data["mappings"]))

    if changed:
        q.version = (q.version or 1) + 1
        q.updated_by_id = actor_id
        log_audit(session, action=AuditAction.edit, actor_id=actor_id,
                  organization_id=q.organization_id, entity_type="question",
                  entity_id=str(q.id), details={"action": "update"})
    return q


def list_revisions(session: Session, question_id) -> list[QuestionRevision]:
    return list(
        session.execute(
            select(QuestionRevision)
            .where(QuestionRevision.question_id == question_id)
            .order_by(QuestionRevision.revision_number.asc())
        ).scalars().all()
    )


def delete_question(session: Session, *, question_id, actor_id) -> None:
    """Soft-delete a question (sets ``deleted_at``). Excluded from list/get."""
    from datetime import datetime, timezone

    q = get_question(session, question_id)
    q.deleted_at = datetime.now(timezone.utc)
    q.updated_by_id = actor_id
    log_audit(session, action=AuditAction.delete, actor_id=actor_id,
              organization_id=q.organization_id, entity_type="question",
              entity_id=str(q.id), details={"action": "soft_delete"})


from app.schemas.question import ReviewAction  # noqa: E402

_TRANSITIONS = {
    ReviewAction.submit: {
        QuestionStatus.draft: QuestionStatus.pending_review,
        QuestionStatus.needs_revision: QuestionStatus.pending_review,
    },
    ReviewAction.approve: {QuestionStatus.pending_review: QuestionStatus.published},
    ReviewAction.request_changes: {QuestionStatus.pending_review: QuestionStatus.needs_revision},
    ReviewAction.archive: {
        QuestionStatus.draft: QuestionStatus.archived,
        QuestionStatus.pending_review: QuestionStatus.archived,
        QuestionStatus.published: QuestionStatus.archived,
        QuestionStatus.needs_revision: QuestionStatus.archived,
    },
    ReviewAction.restore: {QuestionStatus.archived: QuestionStatus.draft},
}

_AUDIT_ACTION = {
    ReviewAction.approve: AuditAction.publish,
    ReviewAction.archive: AuditAction.archive,
}


class IllegalTransition(ValueError):
    """Review action invalid for the current status (maps to HTTP 409)."""


def submit_review(session: Session, *, question_id, actor_id,
                  action: ReviewAction, comment: str | None = None) -> Question:
    q = get_question(session, question_id)
    target = _TRANSITIONS.get(action, {}).get(q.status)
    if target is None:
        raise IllegalTransition(
            f"action {action.value} not allowed from status {q.status.value}"
        )
    q.status = target
    q.updated_by_id = actor_id
    audit_action = _AUDIT_ACTION.get(action, AuditAction.edit)
    log_audit(session, action=audit_action, actor_id=actor_id,
              organization_id=q.organization_id, entity_type="question",
              entity_id=str(q.id), details={"action": action.value, "comment": comment})
    return q
