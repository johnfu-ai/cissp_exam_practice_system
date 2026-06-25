"""Pydantic schemas for the practice API.

Bilingual delivery: stem/options/rationale are `Localized` ({en, zh}) so a
single response can serve en, zh, or bilingual language modes. The session's
`language_mode` is carried in `SessionOut.config` (unchanged) and echoed in
`QuestionDeliveryOut.language_mode`.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import ErrorType

Subset = Literal["all", "unpracticed", "wrong", "bookmarked", "needs_review"]
OrderMode = Literal["random", "sequential", "easy_to_hard"]
LanguageMode = Literal["en", "zh", "bilingual"]


class SessionCreateIn(BaseModel):
    count: int = Field(ge=1, le=200)
    subset: Subset = "all"
    order_mode: OrderMode = "random"
    language_mode: LanguageMode | None = None
    domain_id: uuid.UUID | None = None
    book_id: uuid.UUID | None = None
    chapter_ids: list[uuid.UUID] = Field(default_factory=list)
    question_type: str | None = None
    difficulty: int | None = None
    tag_id: uuid.UUID | None = None


class SessionOut(BaseModel):
    id: uuid.UUID
    status: str
    total_questions: int
    correct_count: int
    started_at: datetime
    ended_at: datetime | None = None
    paused_at: datetime | None = None
    config: dict


class Localized(BaseModel):
    en: str | None = None
    zh: str | None = None


class OptionDelivery(BaseModel):
    id: uuid.UUID
    order_index: int
    content: Localized
    content_format: Localized


class QuestionDeliveryOut(BaseModel):
    session_id: uuid.UUID
    position: int
    total: int
    question_id: uuid.UUID
    question_type: str
    available_languages: list[str]
    language_mode: str
    stem: Localized
    options: list[OptionDelivery]
    elapsed_ms: int
    previous_answer: dict | None = None


class AnswerIn(BaseModel):
    position: int = Field(ge=0)
    selected: list[int]
    started_at: datetime


class PerOptionExplanation(BaseModel):
    order_index: int
    is_correct: bool
    explanation: Localized


class AnswerResultOut(BaseModel):
    is_correct: bool
    correct_indexes: list[int]
    selected_indexes: list[int]
    correct_rationale: Localized
    key_point_summary: Localized
    per_option: list[PerOptionExplanation]
    mapping: dict
    history: list[dict]


class DomainBreakdown(BaseModel):
    domain_id: uuid.UUID | None
    domain_name: str | None
    answered: int
    correct: int


class WrongQuestion(BaseModel):
    question_id: uuid.UUID
    stem: Localized
    selected_indexes: list[int]
    correct_indexes: list[int]


class SessionSummaryOut(BaseModel):
    session_id: uuid.UUID
    total_questions: int
    answered_count: int
    correct_count: int
    accuracy: float
    total_time_spent_ms: int
    domains: list[DomainBreakdown]
    wrong_questions: list[WrongQuestion]


class QuestionStateIn(BaseModel):
    is_bookmarked: bool | None = None
    is_flagged_review: bool | None = None
    is_mastered: bool | None = None
    is_questioned: bool | None = None
    note: str | None = None
    error_type: ErrorType | None = None
