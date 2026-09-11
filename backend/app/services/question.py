"""Question bank service: CRUD, lifecycle, revisions, feedback.

Translations-based: question content (stem, options, rationale) lives in
per-language ``QuestionTranslation`` rows. The canonical ``QuestionOption``
carries only ``order_index`` + ``is_correct`` (the answer key).
``Question.available_languages`` is derived from the translation rows and is
recomputed on every create/update.

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
from app.models.enums import (
    AuditAction,
    QuestionFeedbackStatus,
    QuestionStatus,
    QuestionType,
)
from app.models.question import (
    Question,
    QuestionFeedback,
    QuestionMapping,
    QuestionOption,
    QuestionRevision,
    QuestionTranslation,
)
from app.schemas.question import (
    FeedbackIn,
    MappingsIn,
    OptionIn,
    QuestionCreateIn,
    QuestionUpdateIn,
    ReviewAction,
    TranslationIn,
)
from app.services.audit import log_audit
from app.services.snapshot import snapshot_question


from app.services.errors import NotFound, ValidationError


class IllegalTransition(ValueError):
    """Review action invalid for the current status (maps to HTTP 409)."""


# --- canonical option validation --------------------------------------------


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


# --- translation helpers -----------------------------------------------------


def get_translations(session: Session, question_id) -> list[QuestionTranslation]:
    """Return all translation rows for a question, ordered by language."""
    return list(
        session.execute(
            select(QuestionTranslation)
            .where(QuestionTranslation.question_id == question_id)
            .order_by(QuestionTranslation.language)
        ).scalars().all()
    )


def _recompute_available_languages(session: Session, q: Question) -> None:
    """Derive ``available_languages`` from the current translation rows."""
    langs = [t.language for t in get_translations(session, q.id)]
    q.available_languages = sorted(langs)


def _translation_is_complete(t: TranslationIn, n_options: int) -> bool:
    """FR-LANG-09: a translation is publishable when stem + rationale are
    non-empty, option count matches the canonical key, and every option has
    non-empty content."""
    if not t.stem.strip() or not t.correct_answer_rationale.strip():
        return False
    if len(t.options) != n_options:
        return False
    return all(o.content.strip() for o in t.options)


def _write_translation_rows(
    session: Session, q: Question, translations: list[TranslationIn], option_count: int
) -> None:
    """Persist translation rows, validating stem non-empty and option count."""
    for t in translations:
        if not t.stem.strip():
            raise ValidationError(f"{t.language} stem must not be empty")
        if len(t.options) != option_count:
            raise ValidationError(
                f"{t.language} options must match canonical option count"
            )
        session.add(
            QuestionTranslation(
                question_id=q.id,
                language=t.language,
                stem=t.stem,
                stem_format=t.stem_format,
                correct_answer_rationale=t.correct_answer_rationale,
                key_point_summary=t.key_point_summary,
                further_reading=t.further_reading,
                options=[o.model_dump() for o in t.options],
            )
        )


# --- revision helpers --------------------------------------------------------


def _next_revision_number(session: Session, question_id) -> int:
    last = session.execute(
        select(QuestionRevision.revision_number)
        .where(QuestionRevision.question_id == question_id)
        .order_by(QuestionRevision.revision_number.desc())
    ).scalars().first()
    return (last or 0) + 1


def _write_revision(
    session: Session, q: Question, *, actor_id, change_summary: str | None
) -> QuestionRevision:
    """Capture a pre-edit snapshot of the question (canonical options + all
    translations) into a revision row."""
    options = list(
        session.execute(
            select(QuestionOption)
            .where(QuestionOption.question_id == q.id)
            .order_by(QuestionOption.order_index)
        ).scalars().all()
    )
    translations = get_translations(session, q.id)
    rev = QuestionRevision(
        question_id=q.id,
        revision_number=_next_revision_number(session, q.id),
        snapshot=snapshot_question(q, translations, options),
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
        session.add(
            QuestionMapping(
                question_id=question_id, knowledge_point_id=mappings.knowledge_point_id
            )
        )
    for tag_id in mappings.tag_ids:
        session.add(QuestionMapping(question_id=question_id, tag_id=tag_id))


def _current_options(session: Session, question_id) -> list[QuestionOption]:
    return list(
        session.execute(
            select(QuestionOption)
            .where(QuestionOption.question_id == question_id)
            .order_by(QuestionOption.order_index)
        ).scalars().all()
    )


# --- create / get / list -----------------------------------------------------


def create_question(
    session: Session, *, org_id, actor_id, payload: QuestionCreateIn
) -> Question:
    if not payload.translations:
        raise ValidationError("at least one translation is required")
    _validate_options(payload.question_type, payload.options)
    option_count = len(payload.options)

    q = Question(
        organization_id=org_id,
        question_type=payload.question_type,
        difficulty=payload.difficulty,
        status=QuestionStatus.draft,
        source=payload.source,
        license_status=payload.license_status,
        prompt_items=payload.prompt_items,
        version=1,
        created_by_id=actor_id,
        updated_by_id=actor_id,
        available_languages=sorted({t.language for t in payload.translations}),
    )
    session.add(q)
    session.flush()

    for i, opt in enumerate(payload.options):
        session.add(
            QuestionOption(
                question_id=q.id,
                order_index=opt.order_index if opt.order_index is not None else i,
                is_correct=opt.is_correct,
            )
        )

    _write_translation_rows(session, q, payload.translations, option_count)
    _apply_mappings(session, q.id, payload.mappings)
    _write_revision(session, q, actor_id=actor_id, change_summary="initial creation")

    log_audit(
        session,
        action=AuditAction.edit,
        actor_id=actor_id,
        organization_id=org_id,
        entity_type="question",
        entity_id=str(q.id),
        details={"action": "create"},
    )
    return q


def get_question(session: Session, question_id, *, org_id) -> Question:
    """Return a live question by id. Raises ``NotFound`` if missing, soft-deleted,
    or belonging to a different org (cross-tenant access -> 404; never reveal
    existence)."""
    q = session.get(Question, question_id)
    if q is None or q.deleted_at is not None or q.organization_id != org_id:
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

    ``filters`` may contain any of: status, question_type, difficulty,
    missing_language (questions whose available_languages does NOT contain it),
    search (translation stem ILIKE), domain_id, chapter_id,
    knowledge_point_id, tag_id. Returns (items, total).
    """
    from sqlalchemy import func

    filters = filters or {}
    stmt = select(Question).where(Question.organization_id == org_id, not_deleted(Question))
    if (st := filters.get("status")) is not None:
        stmt = stmt.where(Question.status == st)
    if (qt := filters.get("question_type")) is not None:
        stmt = stmt.where(Question.question_type == qt)
    if (diff := filters.get("difficulty")) is not None:
        stmt = stmt.where(Question.difficulty == diff)
    if (ml := filters.get("missing_language")) is not None:
        # Questions whose available_languages does NOT contain ml.
        stmt = stmt.where(~Question.available_languages.any(ml))
    if (search := filters.get("search")) is not None:
        # Search across translation stems (en/zh).
        stmt = stmt.where(
            Question.id.in_(
                select(QuestionTranslation.question_id).where(
                    QuestionTranslation.stem.ilike(f"%{search}%")
                )
            )
        )
    if (domain_id := filters.get("domain_id")) is not None:
        stmt = stmt.where(
            Question.id.in_(
                select(QuestionMapping.question_id).where(QuestionMapping.domain_id == domain_id)
            )
        )
    if (chapter_id := filters.get("chapter_id")) is not None:
        stmt = stmt.where(
            Question.id.in_(
                select(QuestionMapping.question_id).where(QuestionMapping.chapter_id == chapter_id)
            )
        )
    if (knowledge_point_id := filters.get("knowledge_point_id")) is not None:
        stmt = stmt.where(
            Question.id.in_(
                select(QuestionMapping.question_id).where(
                    QuestionMapping.knowledge_point_id == knowledge_point_id
                )
            )
        )
    if (tag_id := filters.get("tag_id")) is not None:
        stmt = stmt.where(
            Question.id.in_(
                select(QuestionMapping.question_id).where(QuestionMapping.tag_id == tag_id)
            )
        )

    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    page = max(page, 1)
    size = min(max(size, 1), 100)
    items = list(
        session.execute(
            stmt.order_by(Question.created_at.desc()).offset((page - 1) * size).limit(size)
        ).scalars().all()
    )
    return items, total


# --- update / delete ---------------------------------------------------------


def _delete_rows(session: Session, model, question_id) -> None:
    rows = list(
        session.execute(select(model).where(model.question_id == question_id)).scalars().all()
    )
    for r in rows:
        session.delete(r)
    # Flush deletes so subsequent INSERTs of rows with the same unique key
    # (e.g. QuestionTranslation (question_id, language)) don't violate the
    # constraint — SQLAlchemy's unit-of-work emits INSERTs before DELETEs.
    if rows:
        session.flush()


def update_question(
    session: Session, *, question_id, actor_id, payload: QuestionUpdateIn, org_id
) -> Question:
    """Partial update. Writes a pre-edit revision snapshot, bumps version, and
    revalidates options when supplied. Replaces (not appends) translations and
    options when supplied. A no-op payload (nothing set) does not bump the
    version.
    """
    q = get_question(session, question_id, org_id=org_id)
    data = payload.model_dump(exclude_unset=True)
    changed = bool(data)

    if "options" in data:
        opts = [OptionIn(**o) for o in data["options"]]
        qtype = data.get("question_type", q.question_type)
        _validate_options(qtype, opts)

    # capture pre-edit snapshot BEFORE mutating (revision records the prior state)
    if changed:
        _write_revision(session, q, actor_id=actor_id, change_summary="update")

    if "question_type" in data:
        q.question_type = data["question_type"]
    if "difficulty" in data:
        q.difficulty = data["difficulty"]
    if "source" in data:
        q.source = data["source"]
    if "license_status" in data:
        q.license_status = data["license_status"]
    if "prompt_items" in data:
        q.prompt_items = data["prompt_items"]
    if "options" in data:
        _delete_rows(session, QuestionOption, q.id)
        for i, opt in enumerate(opts):
            session.add(
                QuestionOption(
                    question_id=q.id,
                    order_index=opt.order_index if opt.order_index is not None else i,
                    is_correct=opt.is_correct,
                )
            )
    if "translations" in data and data["translations"] is not None:
        langs = {t["language"] for t in data["translations"]}
        if not langs:
            raise ValidationError("at least one translation is required")
        if "options" in data:
            option_count = len(opts)
        else:
            option_count = len(_current_options(session, q.id))
        _delete_rows(session, QuestionTranslation, q.id)
        _write_translation_rows(
            session, q, [TranslationIn(**t) for t in data["translations"]], option_count
        )
    if "mappings" in data:
        _delete_rows(session, QuestionMapping, q.id)
        _apply_mappings(session, q.id, MappingsIn(**data["mappings"]))

    if changed:
        _recompute_available_languages(session, q)
        q.version = (q.version or 1) + 1
        q.updated_by_id = actor_id
        log_audit(
            session,
            action=AuditAction.edit,
            actor_id=actor_id,
            organization_id=q.organization_id,
            entity_type="question",
            entity_id=str(q.id),
            details={"action": "update"},
        )
    return q


def list_revisions(session: Session, question_id) -> list[QuestionRevision]:
    return list(
        session.execute(
            select(QuestionRevision)
            .where(QuestionRevision.question_id == question_id)
            .order_by(QuestionRevision.revision_number.asc())
        ).scalars().all()
    )


def delete_question(session: Session, *, question_id, actor_id, org_id) -> None:
    """Soft-delete a question (sets ``deleted_at``). Excluded from list/get."""
    from datetime import datetime, timezone

    q = get_question(session, question_id, org_id=org_id)
    q.deleted_at = datetime.now(timezone.utc)
    q.updated_by_id = actor_id
    log_audit(
        session,
        action=AuditAction.delete,
        actor_id=actor_id,
        organization_id=q.organization_id,
        entity_type="question",
        entity_id=str(q.id),
        details={"action": "soft_delete"},
    )


# --- review state machine ----------------------------------------------------

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


def submit_review(
    session: Session,
    *,
    question_id,
    actor_id,
    action: ReviewAction,
    comment: str | None = None,
    org_id,
) -> Question:
    q = get_question(session, question_id, org_id=org_id)
    if action == ReviewAction.approve:
        # FR-LANG-09: require >=1 complete translation; if multiple present,
        # all must be complete.
        translations = get_translations(session, q.id)
        options = _current_options(session, q.id)
        n = len(options)
        complete = [
            t
            for t in translations
            if _translation_is_complete(
                TranslationIn(
                    language=t.language,
                    stem=t.stem,
                    correct_answer_rationale=t.correct_answer_rationale,
                    options=t.options,
                ),
                n,
            )
        ]
        if not complete:
            raise ValidationError("cannot publish: no complete translation")
        if len(translations) >= 2 and len(complete) < len(translations):
            raise ValidationError("cannot publish: present translations must all be complete")
    target = _TRANSITIONS.get(action, {}).get(q.status)
    if target is None:
        raise IllegalTransition(
            f"action {action.value} not allowed from status {q.status.value}"
        )
    q.status = target
    q.updated_by_id = actor_id
    audit_action = _AUDIT_ACTION.get(action, AuditAction.edit)
    log_audit(
        session,
        action=audit_action,
        actor_id=actor_id,
        organization_id=q.organization_id,
        entity_type="question",
        entity_id=str(q.id),
        details={"action": action.value, "comment": comment},
    )
    return q


# --- correction feedback -----------------------------------------------------


def create_feedback(
    session: Session,
    *,
    org_id,
    question_id,
    reporter_id,
    payload: FeedbackIn,
) -> QuestionFeedback:
    """Create a correction-feedback entry on a live question (FR-Q-07)."""
    get_question(session, question_id, org_id=org_id)  # raises NotFound if missing/deleted/cross-org
    fb = QuestionFeedback(
        organization_id=org_id,
        question_id=question_id,
        reporter_id=reporter_id,
        feedback_type=payload.feedback_type,
        comment=payload.comment,
        status=QuestionFeedbackStatus.open,
    )
    session.add(fb)
    return fb


def list_feedback(session: Session, *, question_id) -> list[QuestionFeedback]:
    return list(
        session.execute(
            select(QuestionFeedback)
            .where(QuestionFeedback.question_id == question_id, not_deleted(QuestionFeedback))
            .order_by(QuestionFeedback.created_at.desc())
        ).scalars().all()
    )


# --- export (FR-IMP-09) ------------------------------------------------------ #

# Columns of the PRD §10.1 import template, so exports round-trip into
# `/api/etl/upload` imports unchanged.
EXPORT_COLUMNS = [
    "question_text", "question_text_zh", "question_type",
    "option_a", "option_a_zh",
    "option_b", "option_b_zh",
    "option_c", "option_c_zh",
    "option_d", "option_d_zh",
    "option_e", "option_e_zh",
    "option_f", "option_f_zh",
    "correct_answers", "explanation", "explanation_zh",
    "difficulty", "license_status",
    "domain", "knowledge_points", "tags",
    "book", "edition", "chapter", "source",
]
_LETTERS = ("a", "b", "c", "d", "e", "f")


def export_questions(
    session: Session,
    *,
    org_id,
    status=None,
) -> tuple[list[dict], list[dict]]:
    """Export the org's live question bank (FR-IMP-09).

    Returns ``(template_rows, full_records)``: the first shaped exactly like
    the PRD §10.1 CSV import template (round-trippable), the second carrying
    the full structured detail (ids, statuses, mappings) for JSON export.
    Everything is batch-loaded — one query per table, no per-question N+1.
    """
    from app.models.question import Book, Chapter
    from app.models.taxonomy import ExamDomain, KnowledgePoint, Tag

    stmt = select(Question).where(
        Question.organization_id == org_id, not_deleted(Question)
    ).order_by(Question.created_at)
    if status is not None:
        stmt = stmt.where(Question.status == status)
    questions = list(session.execute(stmt).scalars().all())
    if not questions:
        return [], []
    qids = [q.id for q in questions]

    trans_by_q: dict = {}
    for t in session.execute(
        select(QuestionTranslation).where(QuestionTranslation.question_id.in_(qids))
    ).scalars().all():
        trans_by_q.setdefault(t.question_id, {})[t.language] = t

    opts_by_q: dict = {}
    for o in session.execute(
        select(QuestionOption)
        .where(QuestionOption.question_id.in_(qids))
        .order_by(QuestionOption.question_id, QuestionOption.order_index)
    ).scalars().all():
        opts_by_q.setdefault(o.question_id, []).append(o)

    map_by_q: dict = {}
    for m in session.execute(
        select(QuestionMapping).where(QuestionMapping.question_id.in_(qids))
    ).scalars().all():
        map_by_q.setdefault(m.question_id, []).append(m)

    domain_names = {
        d.id: (d.number, d.name)
        for d in session.execute(select(ExamDomain)).scalars().all()
    }
    kp_names = {
        k.id: k.name
        for k in session.execute(select(KnowledgePoint)).scalars().all()
    }
    tag_names = {
        t.id: t.name
        for t in session.execute(select(Tag)).scalars().all()
    }
    chapters = {
        c.id: c
        for c in session.execute(select(Chapter)).scalars().all()
    }
    books = {
        b.id: b
        for b in session.execute(select(Book)).scalars().all()
    }

    def _opt_text(trans, order_index: int) -> str:
        for o in ((trans.options or []) if trans else []):
            if o.get("order_index") == order_index:
                return o.get("content") or ""
        return ""

    def _opt_explanation(trans, order_index: int) -> str:
        for o in ((trans.options or []) if trans else []):
            if o.get("order_index") == order_index:
                return o.get("explanation") or ""
        return ""

    template_rows: list[dict] = []
    full_records: list[dict] = []
    for q in questions:
        en = trans_by_q.get(q.id, {}).get("en")
        zh = trans_by_q.get(q.id, {}).get("zh")
        options = opts_by_q.get(q.id, [])
        mappings = map_by_q.get(q.id, [])

        correct = [
            _LETTERS[o.order_index].upper()
            for o in options
            if o.is_correct and 0 <= o.order_index < len(_LETTERS)
        ]
        domain_id = next((m.domain_id for m in mappings if m.domain_id), None)
        chapter = chapters.get(
            next((m.chapter_id for m in mappings if m.chapter_id), None)
        )
        book = books.get(chapter.book_id) if chapter else None
        kp = "; ".join(
            kp_names[m.knowledge_point_id]
            for m in mappings
            if m.knowledge_point_id and m.knowledge_point_id in kp_names
        )
        tags = "; ".join(
            tag_names[m.tag_id]
            for m in mappings
            if m.tag_id and m.tag_id in tag_names
        )

        row = {col: "" for col in EXPORT_COLUMNS}
        row["question_text"] = en.stem if en else ""
        row["question_text_zh"] = zh.stem if zh else ""
        row["question_type"] = q.question_type.value if q.question_type else "single_choice"
        for o in options:
            if 0 <= o.order_index < len(_LETTERS):
                letter = _LETTERS[o.order_index]
                row[f"option_{letter}"] = _opt_text(en, o.order_index)
                row[f"option_{letter}_zh"] = _opt_text(zh, o.order_index)
        row["correct_answers"] = ",".join(correct)
        row["explanation"] = (en.correct_answer_rationale if en else "") or ""
        row["explanation_zh"] = (zh.correct_answer_rationale if zh else "") or ""
        row["difficulty"] = str(q.difficulty) if q.difficulty is not None else ""
        row["license_status"] = q.license_status.value if q.license_status else ""
        row["domain"] = str(domain_names[domain_id][0]) if domain_id in domain_names else ""
        row["knowledge_points"] = kp
        row["tags"] = tags
        row["book"] = book.title if book else ""
        row["edition"] = book.edition or "" if book else ""
        row["chapter"] = chapter.title if chapter else ""
        row["source"] = q.source or ""
        template_rows.append(row)

        def _lang(t):
            if t is None:
                return None
            return {
                "stem": t.stem,
                "rationale": t.correct_answer_rationale,
                "key_points": t.key_point_summary,
                "options": [
                    {
                        "order_index": o.order_index,
                        "content": _opt_text(t, o.order_index),
                        "explanation": _opt_explanation(t, o.order_index),
                        "is_correct": o.is_correct,
                    }
                    for o in options
                ],
            }

        full_records.append({
            "id": str(q.id),
            "question_type": q.question_type.value if q.question_type else None,
            "status": q.status.value if q.status else None,
            "difficulty": q.difficulty,
            "available_languages": list(q.available_languages or []),
            "source": q.source,
            "license_status": q.license_status.value if q.license_status else None,
            "correct_answers": correct,
            "translations": {"en": _lang(en), "zh": _lang(zh)},
            "mappings": {
                "domain": domain_names.get(domain_id, (None, None))[1],
                "chapter": chapter.title if chapter else None,
                "book": book.title if book else None,
                "knowledge_points": [
                    kp_names[m.knowledge_point_id]
                    for m in mappings
                    if m.knowledge_point_id and m.knowledge_point_id in kp_names
                ],
                "tags": [
                    tag_names[m.tag_id]
                    for m in mappings
                    if m.tag_id and m.tag_id in tag_names
                ],
            },
            "created_at": q.created_at.isoformat() if q.created_at else None,
            "updated_at": q.updated_at.isoformat() if q.updated_at else None,
        })

    return template_rows, full_records
