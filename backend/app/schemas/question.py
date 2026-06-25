"""Pydantic schemas for the question bank API.

Translations-based: question content (stem, options, rationale) lives in
per-language `QuestionTranslation` rows. The canonical `QuestionOption` only
carries `order_index` + `is_correct` (the answer key), so `OptionIn`/`OptionOut`
are canonical-only and each `TranslationOut` carries its own localized options.
"""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.enums import (
    LicenseStatus,
    QuestionFeedbackStatus,
    QuestionFeedbackType,
    QuestionStatus,
    QuestionType,
    TextFormat,
)


# --- Translation-layer schemas (per-language content) ------------------------


class TranslationOptionIn(BaseModel):
    order_index: int
    content: str
    content_format: TextFormat = TextFormat.markdown
    explanation: str | None = None


class TranslationIn(BaseModel):
    language: str  # 'en' | 'zh'
    stem: str
    stem_format: TextFormat = TextFormat.markdown
    correct_answer_rationale: str
    key_point_summary: str | None = None
    further_reading: str | None = None
    options: list[TranslationOptionIn]


class TranslationOptionOut(BaseModel):
    order_index: int
    content: str
    content_format: TextFormat
    explanation: str | None = None


class TranslationOut(BaseModel):
    language: str
    stem: str
    stem_format: TextFormat
    correct_answer_rationale: str
    key_point_summary: str | None = None
    further_reading: str | None = None
    options: list[TranslationOptionOut]


# --- Canonical answer-key schemas (language-independent) ---------------------


class OptionIn(BaseModel):
    """Canonical option: order + correctness only. Content lives per-translation."""

    order_index: int | None = None
    is_correct: bool = False


class OptionOut(BaseModel):
    id: uuid.UUID
    order_index: int
    is_correct: bool


class MappingsIn(BaseModel):
    domain_id: uuid.UUID | None = None
    chapter_id: uuid.UUID | None = None
    knowledge_point_id: uuid.UUID | None = None
    tag_ids: list[uuid.UUID] = Field(default_factory=list)


class MappingsOut(BaseModel):
    domain_id: uuid.UUID | None = None
    chapter_id: uuid.UUID | None = None
    knowledge_point_id: uuid.UUID | None = None
    tag_ids: list[uuid.UUID] = Field(default_factory=list)


# --- Question create/update/out ---------------------------------------------


class QuestionCreateIn(BaseModel):
    question_type: QuestionType
    difficulty: int | None = None
    source: str | None = None
    license_status: LicenseStatus = LicenseStatus.unconfirmed
    prompt_items: list | None = None
    options: list[OptionIn]  # canonical answer key
    translations: list[TranslationIn]  # at least one
    mappings: MappingsIn = Field(default_factory=MappingsIn)


class QuestionUpdateIn(BaseModel):
    question_type: QuestionType | None = None
    difficulty: int | None = None
    source: str | None = None
    license_status: LicenseStatus | None = None
    prompt_items: list | None = None
    options: list[OptionIn] | None = None
    translations: list[TranslationIn] | None = None
    mappings: MappingsIn | None = None


class QuestionOut(BaseModel):
    id: uuid.UUID
    question_type: QuestionType
    difficulty: int | None
    available_languages: list[str]
    status: QuestionStatus
    source: str | None
    license_status: LicenseStatus
    version: int
    prompt_items: list | None = None
    created_at: datetime
    updated_at: datetime
    options: list[OptionOut]  # canonical {id, order_index, is_correct}
    translations: list[TranslationOut]
    mappings: MappingsOut


class QuestionListItem(BaseModel):
    id: uuid.UUID
    question_type: QuestionType
    status: QuestionStatus
    difficulty: int | None
    available_languages: list[str]
    domain_id: uuid.UUID | None = None
    created_at: datetime


# --- Review + feedback + revisions (unchanged) -------------------------------


class ReviewAction(str, Enum):
    submit = "submit"
    approve = "approve"
    request_changes = "request_changes"
    archive = "archive"
    restore = "restore"


class ReviewActionIn(BaseModel):
    action: ReviewAction
    comment: str | None = None


class FeedbackIn(BaseModel):
    feedback_type: QuestionFeedbackType
    comment: str | None = None


class FeedbackOut(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    reporter_id: uuid.UUID | None = None
    feedback_type: QuestionFeedbackType
    comment: str | None = None
    status: QuestionFeedbackStatus
    created_at: datetime


class RevisionOut(BaseModel):
    revision_number: int
    edited_by_id: uuid.UUID | None = None
    edited_at: datetime
    change_summary: str | None = None
    snapshot: dict
