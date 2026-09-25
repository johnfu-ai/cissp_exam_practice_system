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
OrderMode = Literal["random", "sequential", "easy_to_hard", "weak_first"]
LanguageMode = Literal["en", "zh", "bilingual"]


class SessionCreateIn(BaseModel):
    count: int = Field(ge=1, le=200)
    subset: Subset = "all"
    order_mode: OrderMode = "random"
    language_mode: LanguageMode | None = None
    domain_id: uuid.UUID | None = None
    book_id: uuid.UUID | None = None
    chapter_ids: list[uuid.UUID] = Field(default_factory=list)
    knowledge_point_id: uuid.UUID | None = None
    question_type: str | None = None
    difficulty: int | None = None
    tag_id: uuid.UUID | None = None
    # §8.1 practice config: shuffle the display order of options per question.
    # The backend stores the flag; the frontend applies the display permutation
    # (selection/submit stay canonical order_index, so judging is unaffected).
    shuffle_options: bool = False


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
    # FR-ANS-07: the user's existing note for this question, so the runner's
    # notes dialog can pre-load for view/edit (None when no note exists).
    note: str | None = None


class AnswerIn(BaseModel):
    position: int = Field(ge=0)
    # FR-ESSAY-02: choice questions submit `selected`; essay questions submit
    # `answer_text` and self-assess afterwards.
    selected: list[int] = Field(default_factory=list)
    answer_text: str | None = None
    started_at: datetime


class PerOptionExplanation(BaseModel):
    order_index: int
    is_correct: bool
    explanation: Localized


class AnswerResultOut(BaseModel):
    # FR-ESSAY-02: None while an essay answer awaits self-assessment.
    is_correct: bool | None
    correct_indexes: list[int]
    selected_indexes: list[int]
    correct_rationale: Localized
    key_point_summary: Localized
    # FR-ESSAY-02: essay reference answer, surfaced with the practice result.
    reference_answer: Localized | None = None
    per_option: list[PerOptionExplanation]
    mapping: dict
    history: list[dict]


class SelfAssessmentIn(BaseModel):
    """FR-ESSAY-02: learner self-assesses an essay answer right after
    submitting it (reference answer shown by the client first)."""
    correct: bool


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


class RelatedQuestionOut(BaseModel):
    """FR-ANS-08: a same-knowledge-point question recommended for further
    practice. Stem is localized (en/zh) so the client can render in the
    current language mode without an extra fetch."""
    question_id: uuid.UUID
    stem: Localized
    knowledge_point_id: uuid.UUID | None = None


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
