import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey


class ExamBlueprint(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "exam_blueprints"
    __table_args__ = (
        UniqueConstraint("version_label", name="uq_blueprints_version_label"),
    )

    version_label: Mapped[str] = mapped_column(String(50), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    min_items: Mapped[int] = mapped_column(Integer, nullable=False)
    max_items: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    passing_score: Mapped[int] = mapped_column(Integer, nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )


class ExamDomain(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "exam_domains"
    __table_args__ = (
        UniqueConstraint("blueprint_id", "number", name="uq_domains_blueprint_number"),
    )

    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_blueprints.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    weight_pct: Mapped[int] = mapped_column(Integer, nullable=False)


class KnowledgePoint(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "knowledge_points"

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class KnowledgePointDomain(UUIDPrimaryKey, Base):
    __tablename__ = "knowledge_point_domains"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_point_id", "domain_id", name="uq_kp_domain"
        ),
    )

    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False
    )
    domain_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_domains.id", ondelete="CASCADE"), nullable=False
    )


class Tag(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("name", name="uq_tags_name"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
