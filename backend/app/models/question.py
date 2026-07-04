import uuid

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    AuditSubjectMixin,
    Base,
    SoftDeleteMixin,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKey,
)
from app.models.enums import (
    ImportFormat,
    ImportStatus,
    LicenseStatus,
    QuestionFeedbackStatus,
    QuestionFeedbackType,
    QuestionStatus,
    QuestionType,
    TextFormat,
)


class ImportJob(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "import_jobs"

    format: Mapped[ImportFormat] = mapped_column(
        Enum(ImportFormat, name="import_format", create_type=True), nullable=False
    )
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    license_status: Mapped[LicenseStatus] = mapped_column(
        Enum(LicenseStatus, name="license_status", create_type=True),
        nullable=False,
        server_default=LicenseStatus.unconfirmed.value,
    )
    status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus, name="import_status", create_type=True),
        nullable=False,
        server_default=ImportStatus.pending.value,
    )
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    initiated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )


class Book(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "books"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    edition: Mapped[str | None] = mapped_column(String(100), nullable=True)
    author: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class Chapter(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "chapters"

    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)


class Question(
    UUIDPrimaryKey,
    TenantScopedMixin,
    TimestampMixin,
    SoftDeleteMixin,
    AuditSubjectMixin,
    Base,
):
    __tablename__ = "questions"
    __table_args__ = (
        Index(
            "ix_questions_available_languages",
            "available_languages",
            postgresql_using="gin",
        ),
    )

    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type", create_type=True), nullable=False
    )
    difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_languages: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(5)), nullable=True
    )
    status: Mapped[QuestionStatus] = mapped_column(
        Enum(QuestionStatus, name="question_status", create_type=True),
        nullable=False,
        server_default=QuestionStatus.draft.value,
    )
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    license_status: Mapped[LicenseStatus] = mapped_column(
        Enum(LicenseStatus, name="license_status", create_type=True),
        nullable=False,
        server_default=LicenseStatus.unconfirmed.value,
    )
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    prompt_items: Mapped[list | None] = mapped_column(JSONB, nullable=True)


class QuestionOption(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "question_options"
    __table_args__ = (
        Index("ix_question_options_question_id", "question_id"),
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))


class QuestionTranslation(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "question_translations"
    __table_args__ = (
        UniqueConstraint("question_id", "language", name="uq_question_translations_qid_lang"),
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(5), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    stem_format: Mapped[TextFormat] = mapped_column(
        Enum(TextFormat, name="text_format", create_type=True),
        nullable=False,
        server_default=TextFormat.markdown.value,
    )
    correct_answer_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    key_point_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    further_reading: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[list] = mapped_column(JSONB, nullable=False)


class QuestionMapping(UUIDPrimaryKey, Base):
    __tablename__ = "question_mappings"
    __table_args__ = (
        Index("ix_question_mappings_question_id", "question_id"),
        Index("ix_question_mappings_domain_id", "domain_id"),
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    domain_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("exam_domains.id", ondelete="SET NULL"), nullable=True
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True
    )
    knowledge_point_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True
    )
    tag_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tags.id", ondelete="SET NULL"), nullable=True
    )


class QuestionRevision(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "question_revisions"
    __table_args__ = (
        Index("ix_question_revisions_question_id", "question_id"),
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    edited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class QuestionFeedback(
    UUIDPrimaryKey,
    TenantScopedMixin,
    TimestampMixin,
    SoftDeleteMixin,
    Base,
):
    __tablename__ = "question_feedback"
    __table_args__ = (
        Index("ix_question_feedback_question_id", "question_id"),
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    reporter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    feedback_type: Mapped[QuestionFeedbackType] = mapped_column(
        Enum(QuestionFeedbackType, name="question_feedback_type", create_type=True),
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[QuestionFeedbackStatus] = mapped_column(
        Enum(QuestionFeedbackStatus, name="question_feedback_status", create_type=True),
        nullable=False,
        server_default=QuestionFeedbackStatus.open.value,
    )

