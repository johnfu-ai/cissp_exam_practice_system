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
