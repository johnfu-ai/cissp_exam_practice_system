"""Paper (试卷) models — PRD v1.4 FR-PAPER.

A paper is an ordered, per-question-scored list of questions imported from a
paper-bank export (or composed manually later). Papers are org-scoped content:
``(dataset_slug, paper_external_id)`` is unique so ETL loading is idempotent.
"""

import uuid

from sqlalchemy import (
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    Base,
    SoftDeleteMixin,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKey,
)
from app.models.enums import PaperStatus


class Paper(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "papers"
    __table_args__ = (
        UniqueConstraint(
            "dataset_slug",
            "paper_external_id",
            name="uq_papers_dataset_external_id",
        ),
        Index("ix_papers_organization_id", "organization_id"),
    )

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[PaperStatus] = mapped_column(
        Enum(PaperStatus, name="paper_status", create_type=True),
        nullable=False,
        server_default=PaperStatus.published.value,
    )
    # Source attribution for idempotent ETL loading (FR-ETL-18); manual papers
    # may leave both NULL (the unique constraint treats NULLs as distinct).
    dataset_slug: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paper_external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # mock papers 一..八 map to CISSP domains 1..8; NULL for mixed papers.
    domain_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    questions: Mapped[list["PaperQuestion"]] = relationship(
        order_by="PaperQuestion.position",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PaperQuestion(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "paper_questions"
    __table_args__ = (
        UniqueConstraint("paper_id", "position", name="uq_paper_questions_paper_position"),
        Index("ix_paper_questions_question_id", "question_id"),
    )

    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
