"""exam session config

Revision ID: d8e1f2a3b4cd
Revises: c1c2a4a0c8dc
Create Date: 2026-06-23 02:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'd8e1f2a3b4cd'
down_revision = 'c1c2a4a0c8dc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'exam_sessions',
        sa.Column(
            'config',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('exam_sessions', 'config')
