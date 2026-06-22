"""Taxonomy read-only HTTP API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dependencies import CurrentUser, require_permission
from app.schemas.taxonomy import (
    BookOut,
    ChapterOut,
    DomainOut,
    KnowledgePointOut,
)
from app.services import taxonomy as svc

router = APIRouter(prefix="/api", tags=["taxonomy"])


@router.get("/domains", response_model=list[DomainOut])
def domains(
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("question:read")),
):
    return [
        DomainOut(id=d.id, number=d.number, name=d.name, weight_pct=d.weight_pct)
        for d in svc.list_domains(session)
    ]


@router.get("/books", response_model=list[BookOut])
def books(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:read")),
):
    return [
        BookOut(id=b.id, title=b.title, edition=b.edition, author=b.author, publisher=b.publisher)
        for b in svc.list_books(session, org_id=current.org_id)
    ]


@router.get("/books/{book_id}/chapters", response_model=list[ChapterOut])
def chapters(
    book_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:read")),
):
    chapters = svc.list_chapters(session, book_id=book_id, org_id=current.org_id)
    if chapters is None:
        raise HTTPException(status_code=404, detail="book not found")
    return [
        ChapterOut(id=c.id, book_id=c.book_id, order_index=c.order_index, title=c.title)
        for c in chapters
    ]


@router.get("/knowledge-points", response_model=list[KnowledgePointOut])
def knowledge_points(
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("question:read")),
):
    return [
        KnowledgePointOut(id=k.id, name=k.name, description=k.description, parent_id=k.parent_id)
        for k in svc.list_knowledge_points(session)
    ]
