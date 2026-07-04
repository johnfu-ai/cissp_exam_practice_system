import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKey
from app.models.enums import ExamSessionKind, ExamSessionStatus


class ExamSession(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "exam_sessions"
    __table_args__ = (
        Index("ix_exam_sessions_user_status", "user_id", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_blueprints.id"), nullable=False
    )
    session_kind: Mapped[ExamSessionKind] = mapped_column(
        Enum(ExamSessionKind, name="exam_session_kind", create_type=True), nullable=False
    )
    status: Mapped[ExamSessionStatus] = mapped_column(
        Enum(ExamSessionStatus, name="exam_session_status", create_type=True),
        nullable=False,
        server_default=ExamSessionStatus.in_progress.value,
    )
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'")
    )


class ExamAnswer(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "exam_answers"
    __table_args__ = (
        Index("ix_exam_answers_session_id", "session_id"),
        UniqueConstraint(
            "session_id", "question_id", name="uq_exam_answers_session_question"
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), nullable=False)
    question_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    options_snapshot: Mapped[list] = mapped_column(JSONB, nullable=False)
    user_answer: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(nullable=True)
    time_spent_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ability_estimate_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    se_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
