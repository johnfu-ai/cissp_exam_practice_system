"""Read-only taxonomy queries (domains, books, chapters, knowledge points).

Domains and knowledge points are GLOBAL (shared across orgs). Books and chapters
are tenant-scoped (``organization_id``).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.question import Book, Chapter
from app.models.taxonomy import ExamDomain, KnowledgePoint


def list_domains(session: Session) -> list[ExamDomain]:
    return list(
        session.execute(select(ExamDomain).order_by(ExamDomain.number)).scalars().all()
    )


def list_books(session: Session, *, org_id) -> list[Book]:
    return list(
        session.execute(
            select(Book)
            .where(Book.organization_id == org_id)
            .order_by(Book.title)
        ).scalars().all()
    )


def list_chapters(session: Session, *, book_id, org_id) -> list[Chapter] | None:
    """Chapters of a book. Returns ``None`` if the book does not exist in ``org_id``."""
    book = session.get(Book, book_id)
    if book is None or book.organization_id != org_id:
        return None
    return list(
        session.execute(
            select(Chapter)
            .where(Chapter.book_id == book_id)
            .order_by(Chapter.order_index)
        ).scalars().all()
    )


def list_knowledge_points(session: Session) -> list[KnowledgePoint]:
    return list(
        session.execute(select(KnowledgePoint).order_by(KnowledgePoint.name)).scalars().all()
    )
