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
