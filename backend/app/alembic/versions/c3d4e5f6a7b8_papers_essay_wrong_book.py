"""papers, essay question type, wrong-book counters

Revision ID: c3d4e5f6a7b8
Revises: b0c1d2e3f4a5
Create Date: 2026-09-25

PRD v1.4 wave (FR-PAPER/FR-ESSAY/FR-WRONG):
- `essay` value on the native `question_type` enum (问答题)
- `question_translations.reference_answer` (per-language essay reference answer)
- `user_question_states.wrong_count` / `last_wrong_at` (persistent wrong book)
- new `paper_status` enum + `papers` / `paper_questions` tables
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c3d4e5f6a7b8"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enum value additions are idempotent; the new value is not used later in
    # this transaction (PG allows ADD VALUE in a txn from v12 on).
    op.execute("ALTER TYPE question_type ADD VALUE IF NOT EXISTS 'essay'")

    op.add_column(
        "question_translations",
        sa.Column("reference_answer", sa.Text(), nullable=True),
    )
    op.add_column(
        "user_question_states",
        sa.Column(
            "wrong_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
    )
    op.add_column(
        "user_question_states",
        sa.Column("last_wrong_at", sa.DateTime(timezone=True), nullable=True),
    )

    paper_status = postgresql.ENUM(
        "draft", "published", "archived", name="paper_status"
    )
    paper_status.create(op.get_bind(), checkfirst=True)
    # Column-level instance must not re-create the type on table create.
    paper_status_col = postgresql.ENUM(
        "draft", "published", "archived", name="paper_status", create_type=False
    )

    op.create_table(
        "papers",
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("total_score", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "question_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "status",
            paper_status_col,
            server_default="published",
            nullable=False,
        ),
        sa.Column("dataset_slug", sa.String(length=100), nullable=True),
        sa.Column("paper_external_id", sa.String(length=200), nullable=True),
        sa.Column("domain_number", sa.Integer(), nullable=True),
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dataset_slug", "paper_external_id", name="uq_papers_dataset_external_id"
        ),
    )
    op.create_index(
        "ix_papers_organization_id", "papers", ["organization_id"], unique=False
    )

    op.create_table(
        "paper_questions",
        sa.Column(
            "paper_id",
            sa.Uuid(),
            sa.ForeignKey("papers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            sa.Uuid(),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paper_id", "position", name="uq_paper_questions_paper_position"),
    )
    op.create_index(
        "ix_paper_questions_question_id", "paper_questions", ["question_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(
        "ix_paper_questions_question_id", table_name="paper_questions"
    )
    op.drop_table("paper_questions")
    op.drop_index("ix_papers_organization_id", table_name="papers")
    op.drop_table("papers")
    sa.Enum(name="paper_status").drop(op.get_bind(), checkfirst=True)
    op.drop_column("user_question_states", "last_wrong_at")
    op.drop_column("user_question_states", "wrong_count")
    op.drop_column("question_translations", "reference_answer")
    # `essay` enum value: no safe DROP VALUE (see e7a1b2c3d4e5 for precedent) —
    # intentional no-op.
