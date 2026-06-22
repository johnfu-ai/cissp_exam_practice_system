"""Pydantic schemas for the fixed exam API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ExamCreateIn(BaseModel):
    kind: str = Field(default="fixed", pattern="^(fixed|cat)$")
    count: int | None = Field(default=None, ge=1, le=500)


class ExamSessionOut(BaseModel):
    id: uuid.UUID
    status: str
    session_kind: str
    total_questions: int
    correct_count: int
    started_at: datetime
    ended_at: datetime | None = None
    time_remaining_ms: int | None = None
    config: dict


class OptionDelivery(BaseModel):
    id: uuid.UUID
    order_index: int
    content: str
    content_format: str


class QuestionDeliveryOut(BaseModel):
    session_id: uuid.UUID
    position: int
    total: int
    question_id: uuid.UUID
    stem: str
    question_type: str
    options: list[OptionDelivery]
    elapsed_ms: int
    time_remaining_ms: int
    previous_answer: dict | None = None


class ExamAnswerIn(BaseModel):
    position: int = Field(ge=0)
    selected: list[int]
    started_at: datetime


class ExamAnswerAck(BaseModel):
    position: int
    saved: bool
    time_remaining_ms: int
    finished: bool = False


class DomainPerformance(BaseModel):
    domain_id: uuid.UUID | None
    domain_name: str | None
    weight_pct: int | None
    answered: int
    correct: int
    accuracy: float


class WrongQuestion(BaseModel):
    question_id: uuid.UUID
    stem: str
    selected_indexes: list[int]
    correct_indexes: list[int]


class ExamReportOut(BaseModel):
    session_id: uuid.UUID
    status: str
    total_questions: int
    answered_count: int
    correct_count: int
    scaled_score: int
    max_score: int
    passing_score: int
    passed: bool
    accuracy: float
    total_time_ms: int
    avg_time_ms: float
    domains: list[DomainPerformance]
    wrong_questions: list[WrongQuestion]
    # CAT-only (None for fixed exams):
    ability_estimate: float | None = None
    ability_ci_lower: float | None = None
    ability_ci_upper: float | None = None
    sem: float | None = None
    readiness_level: str | None = None
    disclaimer: str | None = None


class ReviewOption(BaseModel):
    order_index: int
    content: str
    is_correct: bool
    explanation: str | None = None


class ReviewItemOut(BaseModel):
    position: int
    question_id: uuid.UUID
    stem: str
    question_type: str
    options: list[ReviewOption]
    correct_rationale: str | None = None
    key_point_summary: str | None = None
    your_answer: dict | None = None
    time_spent_ms: int | None = None


class ExamHistoryItemOut(BaseModel):
    id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None = None
    status: str
    total_questions: int
    correct_count: int
    scaled_score: int
    max_score: int
    passed: bool
    accuracy: float
