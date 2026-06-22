from __future__ import annotations
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel


class DashboardOut(BaseModel):
    practiced_questions: int
    total_answered: int
    correct_count: int
    accuracy: float
    study_time_ms: int
    streak_days: int
    last_active_at: datetime | None


class DomainMasteryOut(BaseModel):
    domain_id: UUID
    number: int
    name: str
    weight_pct: int
    answered: int
    correct: int
    accuracy: float
    avg_time_ms: int
    mastery_level: str


class TrendPoint(BaseModel):
    date: date
    answered: int
    correct: int
    accuracy: float


class TrendOut(BaseModel):
    window_days: int
    points: list[TrendPoint]


class WeakAreaOut(BaseModel):
    domain_id: UUID | None
    knowledge_point_id: UUID | None
    label: str
    answered: int
    correct: int
    accuracy: float


class WeakAreasOut(BaseModel):
    weak_domains: list[WeakAreaOut]
    weak_knowledge_points: list[WeakAreaOut]


class ErrorTypeBreakdown(BaseModel):
    error_type: str | None
    count: int


class ErrorTypeOut(BaseModel):
    total_wrong_classified: int
    distribution: list[ErrorTypeBreakdown]


class ReviewRecommendationOut(BaseModel):
    focus_domain: WeakAreaOut | None
    wrong_to_review: list[UUID]
    next_practice_question_ids: list[UUID]
    rationale: str


class PersonalReportOut(BaseModel):
    generated_at: datetime
    dashboard: DashboardOut
    domains: list[DomainMasteryOut]
    trend_30d: TrendOut
    weak_areas: WeakAreasOut
    error_types: ErrorTypeOut
    recommendation: ReviewRecommendationOut
