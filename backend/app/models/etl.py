import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKey,
)
from app.models.enums import EtlRunPhase, ImportFormat


class EtlDataset(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "etl_datasets"
    __table_args__ = (UniqueConstraint("slug", name="uq_etl_datasets_slug"),)

    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str] = mapped_column(String(500), nullable=False)
    format: Mapped[ImportFormat] = mapped_column(
        Enum(ImportFormat, name="import_format", create_type=False), nullable=False
    )
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    languages: Mapped[list[str]] = mapped_column(ARRAY(String(5)), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class EtlRun(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "etl_runs"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("etl_datasets.id"), nullable=False
    )
    import_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_jobs.id"), nullable=False
    )
    phase: Mapped[EtlRunPhase] = mapped_column(
        Enum(EtlRunPhase, name="etl_run_phase", create_type=True), nullable=False
    )
    preview_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class QuestionExternalKey(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "question_external_keys"
    __table_args__ = (
        UniqueConstraint(
            "dataset_slug", "external_id", "language", name="uq_qek_dataset_ext_lang"
        ),
    )

    dataset_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    language: Mapped[str] = mapped_column(String(5), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )


class ChapterDomainMapping(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "chapter_domain_mappings"
    __table_args__ = (
        UniqueConstraint(
            "dataset_slug", "chapter_number", name="uq_cdm_dataset_chapter"
        ),
    )

    dataset_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    domain_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("exam_domains.id", ondelete="SET NULL"), nullable=True
    )
    chapter_title: Mapped[str] = mapped_column(String(500), nullable=False)
