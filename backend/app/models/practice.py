import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKey
from app.models.enums import ErrorType, MasteryLevel, PracticeSessionStatus


class PracticeSession(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "practice_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[PracticeSessionStatus] = mapped_column(
        Enum(PracticeSessionStatus, name="practice_session_status", create_type=True),
        nullable=False,
        server_default=PracticeSessionStatus.in_progress.value,
    )
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PracticeAnswer(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "practice_answers"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), nullable=False)
    question_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    options_snapshot: Mapped[list] = mapped_column(JSONB, nullable=False)
    user_answer: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(nullable=True)
    time_spent_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class UserQuestionState(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "user_question_states"
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_user_question_state"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), nullable=False)
    is_bookmarked: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    is_flagged_review: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    is_mastered: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    is_questioned: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    mastery_level: Mapped[MasteryLevel] = mapped_column(
        Enum(MasteryLevel, name="mastery_level", create_type=True),
        nullable=False,
        server_default=MasteryLevel.not_started.value,
    )
    error_type: Mapped[ErrorType | None] = mapped_column(
        Enum(ErrorType, name="error_type", create_type=True), nullable=True
    )
