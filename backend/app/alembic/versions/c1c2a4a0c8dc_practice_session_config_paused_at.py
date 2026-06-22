"""practice session config + paused_at

Revision ID: c1c2a4a0c8dc
Revises: 50a14663f11a
Create Date: 2026-06-23 01:19:39.277473
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'c1c2a4a0c8dc'
down_revision = '50a14663f11a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'practice_sessions',
        sa.Column(
            'config',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.add_column(
        'practice_sessions',
        sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('practice_sessions', 'paused_at')
    op.drop_column('practice_sessions', 'config')
