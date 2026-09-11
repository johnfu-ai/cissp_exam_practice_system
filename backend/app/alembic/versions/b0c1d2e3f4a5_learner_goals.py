"""FR-USER-06 learner goals: exam target date + daily practice goal

Adds nullable ``users.exam_target_date`` (DATE) and
``users.daily_goal_answers`` (INT) — null means "not set", so existing rows
and clients are unaffected.

Revision ID: b0c1d2e3f4a5
Revises: a9b8c7d6e5f4
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b0c1d2e3f4a5"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("exam_target_date", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("daily_goal_answers", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "daily_goal_answers")
    op.drop_column("users", "exam_target_date")
