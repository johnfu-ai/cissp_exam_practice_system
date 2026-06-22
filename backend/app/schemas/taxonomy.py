"""Pydantic schemas for the taxonomy read API."""

import uuid

from pydantic import BaseModel


class DomainOut(BaseModel):
    id: uuid.UUID
    number: int
    name: str
    weight_pct: int


class BookOut(BaseModel):
    id: uuid.UUID
    title: str
    edition: str | None = None
    author: str | None = None
    publisher: str | None = None


class ChapterOut(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    order_index: int
    title: str


class KnowledgePointOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    parent_id: uuid.UUID | None = None
