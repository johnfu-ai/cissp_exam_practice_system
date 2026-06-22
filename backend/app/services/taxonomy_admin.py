"""Taxonomy admin write operations (sub-project D).

All write logic, validation, and audit logging for the taxonomy subsystem.
Global taxonomy (blueprints/domains/knowledge-points/bindings/tags) is not
org-scoped; books/chapters are tenant-scoped. Every mutation is audit-logged.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import AuditAction
from app.models.question import Book, Chapter, QuestionMapping
from app.models.taxonomy import (
    ExamBlueprint,
    ExamDomain,
    KnowledgePoint,
    KnowledgePointDomain,
    Tag,
)
from app.schemas.taxonomy import (
    BlueprintIn,
    BlueprintUpdateIn,
    BindingIn,
    BookIn,
    ChapterIn,
    DomainIn,
    KnowledgePointIn,
    TagIn,
)
from app.services.audit import log_audit


class ValidationError(ValueError):
    """Invalid input (maps to HTTP 422)."""


class NotFound(LookupError):
    """Entity not found (maps to HTTP 404)."""


class ConflictError(ValueError):
    """Operation conflicts with existing data (maps to HTTP 409)."""


# --- ExamBlueprint ---


def _validate_blueprint_fields(
    *,
    min_items,
    max_items,
    duration_minutes,
    passing_score,
    max_score,
    version_label,
):
    if not version_label or not version_label.strip():
        raise ValidationError("version_label is required")
    if min_items <= 0 or max_items <= 0 or min_items > max_items:
        raise ValidationError("require 0 < min_items <= max_items")
    if duration_minutes <= 0:
        raise ValidationError("duration_minutes must be positive")
    if not (0 < passing_score < max_score):
        raise ValidationError("require 0 < passing_score < max_score")


def create_blueprint(session: Session, *, actor_id, payload: BlueprintIn) -> ExamBlueprint:
    _validate_blueprint_fields(
        min_items=payload.min_items,
        max_items=payload.max_items,
        duration_minutes=payload.duration_minutes,
        passing_score=payload.passing_score,
        max_score=payload.max_score,
        version_label=payload.version_label,
    )
    bp = ExamBlueprint(
        version_label=payload.version_label,
        effective_date=payload.effective_date,
        min_items=payload.min_items,
        max_items=payload.max_items,
        duration_minutes=payload.duration_minutes,
        passing_score=payload.passing_score,
        max_score=payload.max_score,
        is_current=False,
    )
    session.add(bp)
    session.flush()
    log_audit(
        session,
        action=AuditAction.config_change,
        actor_id=actor_id,
        entity_type="exam_blueprint",
        entity_id=str(bp.id),
        details={"op": "create", "version_label": bp.version_label},
    )
    return bp


def list_blueprints(session: Session) -> list[ExamBlueprint]:
    return list(
        session.execute(
            select(ExamBlueprint).order_by(ExamBlueprint.effective_date.desc())
        ).scalars().all()
    )


def get_blueprint(session: Session, blueprint_id) -> ExamBlueprint:
    bp = session.get(ExamBlueprint, blueprint_id)
    if bp is None:
        raise NotFound("blueprint not found")
    return bp


def update_blueprint(
    session: Session,
    *,
    blueprint_id,
    actor_id,
    payload: BlueprintUpdateIn,
) -> ExamBlueprint:
    bp = get_blueprint(session, blueprint_id)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return bp
    # is_current is never set via update -- only via set-current.
    data.pop("is_current", None)
    merged = dict(
        version_label=bp.version_label,
        effective_date=bp.effective_date,
        min_items=bp.min_items,
        max_items=bp.max_items,
        duration_minutes=bp.duration_minutes,
        passing_score=bp.passing_score,
        max_score=bp.max_score,
    )
    merged.update(data)
    _validate_blueprint_fields(
        min_items=merged["min_items"],
        max_items=merged["max_items"],
        duration_minutes=merged["duration_minutes"],
        passing_score=merged["passing_score"],
        max_score=merged["max_score"],
        version_label=merged["version_label"],
    )
    for k, v in data.items():
        setattr(bp, k, v)
    session.flush()
    log_audit(
        session,
        action=AuditAction.config_change,
        actor_id=actor_id,
        entity_type="exam_blueprint",
        entity_id=str(bp.id),
        details={"op": "update", "fields": list(data.keys())},
    )
    return bp


def set_current_blueprint(
    session: Session, *, blueprint_id, actor_id
) -> ExamBlueprint:
    bp = get_blueprint(session, blueprint_id)
    others = session.execute(
        select(ExamBlueprint).where(ExamBlueprint.is_current.is_(True))
    ).scalars().all()
    for o in others:
        o.is_current = False
    bp.is_current = True
    session.flush()
    log_audit(
        session,
        action=AuditAction.config_change,
        actor_id=actor_id,
        entity_type="exam_blueprint",
        entity_id=str(bp.id),
        details={"op": "set_current"},
    )
    return bp


def _blueprint_has_mapped_questions(session: Session, blueprint_id) -> bool:
    domain_ids = select(ExamDomain.id).where(ExamDomain.blueprint_id == blueprint_id)
    exists = session.execute(
        select(QuestionMapping.question_id)
        .where(QuestionMapping.domain_id.in_(domain_ids))
        .limit(1)
    ).first()
    return exists is not None


def delete_blueprint(session: Session, *, blueprint_id, actor_id) -> None:
    bp = get_blueprint(session, blueprint_id)
    if bp.is_current:
        raise ConflictError("cannot delete the current blueprint")
    if _blueprint_has_mapped_questions(session, blueprint_id):
        raise ConflictError("blueprint has domains referenced by questions")
    session.delete(bp)
    session.flush()
    log_audit(
        session,
        action=AuditAction.config_change,
        actor_id=actor_id,
        entity_type="exam_blueprint",
        entity_id=str(blueprint_id),
        details={"op": "delete"},
    )


# --- ExamDomain ---


def _validate_domain(*, number, name, weight_pct):
    if number < 1:
        raise ValidationError("domain number must be >= 1")
    if not name or not name.strip():
        raise ValidationError("domain name is required")
    if not (0 <= weight_pct <= 100):
        raise ValidationError("weight_pct must be 0..100")


def create_domain(
    session: Session, *, blueprint_id, actor_id, payload: DomainIn
) -> ExamDomain:
    get_blueprint(session, blueprint_id)  # raises NotFound
    _validate_domain(
        number=payload.number, name=payload.name, weight_pct=payload.weight_pct
    )
    dup = session.execute(
        select(ExamDomain).where(
            ExamDomain.blueprint_id == blueprint_id, ExamDomain.number == payload.number
        )
    ).first()
    if dup is not None:
        raise ConflictError("domain number already exists in blueprint")
    d = ExamDomain(
        blueprint_id=blueprint_id,
        number=payload.number,
        name=payload.name,
        weight_pct=payload.weight_pct,
    )
    session.add(d)
    session.flush()
    log_audit(
        session,
        action=AuditAction.config_change,
        actor_id=actor_id,
        entity_type="exam_domain",
        entity_id=str(d.id),
        details={"op": "create", "blueprint_id": str(blueprint_id)},
    )
    return d


def list_domains_for_blueprint(session: Session, blueprint_id) -> list[ExamDomain]:
    get_blueprint(session, blueprint_id)
    return list(
        session.execute(
            select(ExamDomain)
            .where(ExamDomain.blueprint_id == blueprint_id)
            .order_by(ExamDomain.number)
        ).scalars().all()
    )


def _get_domain(session: Session, blueprint_id, domain_id) -> ExamDomain:
    d = session.execute(
        select(ExamDomain).where(
            ExamDomain.id == domain_id, ExamDomain.blueprint_id == blueprint_id
        )
    ).scalar_one_or_none()
    if d is None:
        raise NotFound("domain not found")
    return d


def update_domain(
    session: Session, *, blueprint_id, domain_id, actor_id, payload: DomainIn
) -> ExamDomain:
    d = _get_domain(session, blueprint_id, domain_id)
    _validate_domain(
        number=payload.number, name=payload.name, weight_pct=payload.weight_pct
    )
    if payload.number != d.number:
        dup = session.execute(
            select(ExamDomain).where(
                ExamDomain.blueprint_id == blueprint_id,
                ExamDomain.number == payload.number,
            )
        ).first()
        if dup is not None:
            raise ConflictError("domain number already exists in blueprint")
    d.number = payload.number
    d.name = payload.name
    d.weight_pct = payload.weight_pct
    session.flush()
    log_audit(
        session,
        action=AuditAction.config_change,
        actor_id=actor_id,
        entity_type="exam_domain",
        entity_id=str(d.id),
        details={"op": "update"},
    )
    return d


def _domain_has_mapped_questions(session: Session, domain_id) -> bool:
    exists = session.execute(
        select(QuestionMapping.question_id)
        .where(QuestionMapping.domain_id == domain_id)
        .limit(1)
    ).first()
    return exists is not None


def delete_domain(
    session: Session, *, blueprint_id, domain_id, actor_id
) -> None:
    d = _get_domain(session, blueprint_id, domain_id)
    if _domain_has_mapped_questions(session, domain_id):
        raise ConflictError("domain is referenced by questions")
    session.delete(d)
    session.flush()
    log_audit(
        session,
        action=AuditAction.config_change,
        actor_id=actor_id,
        entity_type="exam_domain",
        entity_id=str(domain_id),
        details={"op": "delete"},
    )


# --- Book + Chapter (tenant-scoped) ---


def _chapter_has_mapped_questions(session: Session, chapter_id) -> bool:
    exists = session.execute(
        select(QuestionMapping.question_id)
        .where(QuestionMapping.chapter_id == chapter_id)
        .limit(1)
    ).first()
    return exists is not None


def create_book(
    session: Session, *, org_id, actor_id, payload: BookIn
) -> Book:
    if not payload.title or not payload.title.strip():
        raise ValidationError("book title is required")
    book = Book(
        organization_id=org_id,
        title=payload.title,
        edition=payload.edition,
        author=payload.author,
        publisher=payload.publisher,
        source_url=payload.source_url,
    )
    session.add(book)
    session.flush()
    log_audit(
        session,
        action=AuditAction.config_change,
        actor_id=actor_id,
        organization_id=org_id,
        entity_type="book",
        entity_id=str(book.id),
        details={"op": "create"},
    )
    return book


def get_book(session: Session, *, book_id, org_id) -> Book:
    book = session.get(Book, book_id)
    if book is None or book.organization_id != org_id:
        raise NotFound("book not found")
    return book


def update_book(
    session: Session, *, book_id, org_id, actor_id, payload: BookIn
) -> Book:
    book = get_book(session, book_id=book_id, org_id=org_id)
    if not payload.title or not payload.title.strip():
        raise ValidationError("book title is required")
    book.title = payload.title
    book.edition = payload.edition
    book.author = payload.author
    book.publisher = payload.publisher
    book.source_url = payload.source_url
    session.flush()
    log_audit(
        session,
        action=AuditAction.edit,
        actor_id=actor_id,
        organization_id=org_id,
        entity_type="book",
        entity_id=str(book.id),
        details={"op": "update"},
    )
    return book


def delete_book(session: Session, *, book_id, org_id, actor_id) -> None:
    book = get_book(session, book_id=book_id, org_id=org_id)
    chapter_ids = select(Chapter.id).where(Chapter.book_id == book_id)
    blocked = session.execute(
        select(QuestionMapping.question_id)
        .where(QuestionMapping.chapter_id.in_(chapter_ids))
        .limit(1)
    ).first()
    if blocked is not None:
        raise ConflictError("book has chapters referenced by questions")
    session.delete(book)
    session.flush()
    log_audit(
        session,
        action=AuditAction.delete,
        actor_id=actor_id,
        organization_id=org_id,
        entity_type="book",
        entity_id=str(book_id),
        details={"op": "delete"},
    )


def create_chapter(
    session: Session, *, book_id, org_id, actor_id, payload: ChapterIn
) -> Chapter:
    book = get_book(session, book_id=book_id, org_id=org_id)
    if payload.order_index < 0:
        raise ValidationError("order_index must be >= 0")
    if not payload.title or not payload.title.strip():
        raise ValidationError("chapter title is required")
    ch = Chapter(
        organization_id=org_id,
        book_id=book.id,
        order_index=payload.order_index,
        title=payload.title,
    )
    session.add(ch)
    session.flush()
    log_audit(
        session,
        action=AuditAction.config_change,
        actor_id=actor_id,
        organization_id=org_id,
        entity_type="chapter",
        entity_id=str(ch.id),
        details={"op": "create"},
    )
    return ch


def _get_chapter(session: Session, *, book_id, chapter_id, org_id) -> Chapter:
    ch = session.execute(
        select(Chapter).where(
            Chapter.id == chapter_id,
            Chapter.book_id == book_id,
            Chapter.organization_id == org_id,
        )
    ).scalar_one_or_none()
    if ch is None:
        raise NotFound("chapter not found")
    return ch


def update_chapter(
    session: Session, *, book_id, chapter_id, org_id, actor_id, payload: ChapterIn
) -> Chapter:
    ch = _get_chapter(
        session, book_id=book_id, chapter_id=chapter_id, org_id=org_id
    )
    if payload.order_index < 0:
        raise ValidationError("order_index must be >= 0")
    if not payload.title or not payload.title.strip():
        raise ValidationError("chapter title is required")
    ch.order_index = payload.order_index
    ch.title = payload.title
    session.flush()
    log_audit(
        session,
        action=AuditAction.edit,
        actor_id=actor_id,
        organization_id=org_id,
        entity_type="chapter",
        entity_id=str(ch.id),
        details={"op": "update"},
    )
    return ch


def delete_chapter(
    session: Session, *, book_id, chapter_id, org_id, actor_id
) -> None:
    ch = _get_chapter(
        session, book_id=book_id, chapter_id=chapter_id, org_id=org_id
    )
    if _chapter_has_mapped_questions(session, chapter_id):
        raise ConflictError("chapter is referenced by questions")
    session.delete(ch)
    session.flush()
    log_audit(
        session,
        action=AuditAction.delete,
        actor_id=actor_id,
        organization_id=org_id,
        entity_type="chapter",
        entity_id=str(chapter_id),
        details={"op": "delete"},
    )


# --- KnowledgePoint (tree) ---


def _validate_kp(*, name):
    if not name or not name.strip():
        raise ValidationError("knowledge point name is required")


def _would_cycle(session: Session, kp_id, proposed_parent_id) -> bool:
    """True if setting kp_id's parent to proposed_parent_id creates a cycle.

    Walk up from proposed_parent; if we hit kp_id, it's a cycle.
    """
    if proposed_parent_id is None:
        return False
    cursor = proposed_parent_id
    seen = set()
    while cursor is not None and cursor not in seen:
        if cursor == kp_id:
            return True
        seen.add(cursor)
        row = session.execute(
            select(KnowledgePoint.parent_id).where(KnowledgePoint.id == cursor)
        ).first()
        if row is None:
            return False
        cursor = row[0]
    return False


def create_knowledge_point(
    session: Session, *, actor_id, payload: KnowledgePointIn
) -> KnowledgePoint:
    _validate_kp(name=payload.name)
    if payload.parent_id is not None:
        parent = session.get(KnowledgePoint, payload.parent_id)
        if parent is None:
            raise NotFound("parent knowledge point not found")
    kp = KnowledgePoint(
        name=payload.name,
        description=payload.description,
        parent_id=payload.parent_id,
    )
    session.add(kp)
    session.flush()
    log_audit(
        session,
        action=AuditAction.config_change,
        actor_id=actor_id,
        entity_type="knowledge_point",
        entity_id=str(kp.id),
        details={"op": "create"},
    )
    return kp


def get_knowledge_point(session: Session, kp_id) -> KnowledgePoint:
    kp = session.get(KnowledgePoint, kp_id)
    if kp is None:
        raise NotFound("knowledge point not found")
    return kp


def update_knowledge_point(
    session: Session, *, kp_id, actor_id, payload: KnowledgePointIn
) -> KnowledgePoint:
    kp = get_knowledge_point(session, kp_id)
    _validate_kp(name=payload.name)
    if payload.parent_id is not None:
        if payload.parent_id == kp_id:
            raise ValidationError("knowledge point cannot be its own parent")
        parent = session.get(KnowledgePoint, payload.parent_id)
        if parent is None:
            raise NotFound("parent knowledge point not found")
        if _would_cycle(session, kp_id, payload.parent_id):
            raise ValidationError("setting this parent would create a cycle")
    kp.name = payload.name
    kp.description = payload.description
    kp.parent_id = payload.parent_id
    session.flush()
    log_audit(
        session,
        action=AuditAction.config_change,
        actor_id=actor_id,
        entity_type="knowledge_point",
        entity_id=str(kp.id),
        details={"op": "update"},
    )
    return kp


def _kp_has_children(session: Session, kp_id) -> bool:
    exists = session.execute(
        select(KnowledgePoint.id).where(KnowledgePoint.parent_id == kp_id).limit(1)
    ).first()
    return exists is not None


def _kp_has_bindings(session: Session, kp_id) -> bool:
    exists = session.execute(
        select(KnowledgePointDomain.domain_id)
        .where(KnowledgePointDomain.knowledge_point_id == kp_id)
        .limit(1)
    ).first()
    return exists is not None


def _kp_has_mapped_questions(session: Session, kp_id) -> bool:
    exists = session.execute(
        select(QuestionMapping.question_id)
        .where(QuestionMapping.knowledge_point_id == kp_id)
        .limit(1)
    ).first()
    return exists is not None


def delete_knowledge_point(session: Session, *, kp_id, actor_id) -> None:
    kp = get_knowledge_point(session, kp_id)
    if _kp_has_children(session, kp_id):
        raise ConflictError("knowledge point has children")
    if _kp_has_bindings(session, kp_id):
        raise ConflictError("knowledge point has domain bindings")
    if _kp_has_mapped_questions(session, kp_id):
        raise ConflictError("knowledge point is referenced by questions")
    session.delete(kp)
    session.flush()
    log_audit(
        session,
        action=AuditAction.config_change,
        actor_id=actor_id,
        entity_type="knowledge_point",
        entity_id=str(kp_id),
        details={"op": "delete"},
    )
