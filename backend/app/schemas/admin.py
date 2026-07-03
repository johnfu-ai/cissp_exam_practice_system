from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import QuestionFeedbackStatus, RoleName, UserStatus


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    status: str
    default_organization_id: uuid.UUID | None
    roles: list[str]


class UserStatusIn(BaseModel):
    status: UserStatus


class UserRolesIn(BaseModel):
    role_names: list[RoleName]


class AdminResetPasswordIn(BaseModel):
    """Admin-assisted password reset. If new_password is omitted, the service
    generates a random one and returns it (the admin relays it out-of-band)."""
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class ClassOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    instructor_id: uuid.UUID | None
    organization_id: uuid.UUID
    member_count: int


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    instructor_id: uuid.UUID | None = None


class ClassMemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str | None


class CatParamsVersionOut(BaseModel):
    id: uuid.UUID
    version_label: str
    effective_date: date
    is_current: bool
    params: dict


class CatParams(BaseModel):
    k0: float = Field(gt=0)
    decay: float = Field(ge=0)
    base_se: float = Field(gt=0)
    early_stop_enabled: bool = True


class CatParamsIn(BaseModel):
    version_label: str = Field(min_length=1, max_length=50)
    effective_date: date
    params: CatParams
    set_current: bool = True


class FeedbackOut(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    reporter_id: uuid.UUID | None
    feedback_type: str
    comment: str | None
    status: str
    created_at: datetime


class FeedbackResolveIn(BaseModel):
    status: QuestionFeedbackStatus
    comment: str | None = None

    @field_validator("status")
    @classmethod
    def _must_be_terminal(cls, v: QuestionFeedbackStatus) -> QuestionFeedbackStatus:
        if v not in (QuestionFeedbackStatus.resolved, QuestionFeedbackStatus.wont_fix):
            raise ValueError("status must be resolved or wont_fix")
        return v


class QualityDashboardOut(BaseModel):
    open_feedback_count: int
    low_accuracy_question_count: int
    missing_explanation_count: int
    disputed_question_count: int


class LowAccuracyQuestionOut(BaseModel):
    question_id: uuid.UUID
    stem: str
    answered: int
    correct: int
    accuracy: float


class MissingExplanationQuestionOut(BaseModel):
    question_id: uuid.UUID
    stem: str
    status: str


class AuditLogOut(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    action: str
    actor_id: uuid.UUID | None
    organization_id: uuid.UUID | None
    entity_type: str | None
    entity_id: str | None
    details: dict | None
    ip_address: str | None


class PaginatedAudit(BaseModel):
    items: list[AuditLogOut]
    total: int
    limit: int
    offset: int


class ReportSummaryOut(BaseModel):
    scope: str
    window_days: int
    active_users: int
    practice_session_count: int
    exam_session_count: int
    total_answers: int
    correct_answers: int
    accuracy: float
    published_question_count: int
    used_question_count: int
    question_bank_usage_pct: float
    top_error_questions: list[LowAccuracyQuestionOut]
