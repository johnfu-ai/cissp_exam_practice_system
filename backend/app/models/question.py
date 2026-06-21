import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
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

    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type", create_type=True), nullable=False
    )
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    stem_format: Mapped[TextFormat] = mapped_column(
        Enum(TextFormat, name="text_format", create_type=True),
        nullable=False,
        server_default=TextFormat.markdown.value,
    )
    difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str] = mapped_column(String(5), nullable=False, server_default=text("'en'"))
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


class QuestionOption(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "question_options"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_format: Mapped[TextFormat] = mapped_column(
        Enum(TextFormat, name="text_format", create_type=True),
        nullable=False,
        server_default=TextFormat.markdown.value,
    )
    is_correct: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)


class Explanation(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "explanations"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    correct_answer_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    key_point_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    further_reading: Mapped[str | None] = mapped_column(Text, nullable=True)


class QuestionMapping(UUIDPrimaryKey, Base):
    __tablename__ = "question_mappings"

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

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    edited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
