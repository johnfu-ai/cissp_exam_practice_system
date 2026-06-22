"""Pydantic schemas for the taxonomy API (read + admin write)."""

import uuid
from datetime import date

from pydantic import BaseModel


class DomainOut(BaseModel):
    id: uuid.UUID
    blueprint_id: uuid.UUID
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


# --- Admin write schemas (sub-project D) ---


class BlueprintIn(BaseModel):
    version_label: str
    effective_date: date
    min_items: int
    max_items: int
    duration_minutes: int
    passing_score: int
    max_score: int


class BlueprintUpdateIn(BaseModel):
    version_label: str | None = None
    effective_date: date | None = None
    min_items: int | None = None
    max_items: int | None = None
    duration_minutes: int | None = None
    passing_score: int | None = None
    max_score: int | None = None


class BlueprintOut(BaseModel):
    id: uuid.UUID
    version_label: str
    effective_date: date
    min_items: int
    max_items: int
    duration_minutes: int
    passing_score: int
    max_score: int
    is_current: bool
    domains: list[DomainOut] = []


class DomainIn(BaseModel):
    number: int
    name: str
    weight_pct: int


class BookIn(BaseModel):
    title: str
    edition: str | None = None
    author: str | None = None
    publisher: str | None = None
    source_url: str | None = None


class ChapterIn(BaseModel):
    order_index: int
    title: str


class KnowledgePointIn(BaseModel):
    name: str
    description: str | None = None
    parent_id: uuid.UUID | None = None


class TagIn(BaseModel):
    name: str
    description: str | None = None


class BindingIn(BaseModel):
    domain_id: uuid.UUID
