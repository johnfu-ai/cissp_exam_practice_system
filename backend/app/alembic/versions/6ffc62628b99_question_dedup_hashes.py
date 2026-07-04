"""question dedup hashes

Revision ID: 6ffc62628b99
Revises: 2f0684f4fbb6
Create Date: 2026-07-04 09:30:43.273487
"""
from alembic import op
import sqlalchemy as sa


revision = '6ffc62628b99'
down_revision = '2f0684f4fbb6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Three-level dedup (PRD §10.4 rule 6 / FR-ETL-08): indexed stem_hash +
    # option_fingerprint on questions. `uq_users_email_lower` is the hand-written
    # functional index filtered by the no-drift test; not touched here.
    op.add_column('questions', sa.Column('stem_hash', sa.String(length=64), nullable=True))
    op.add_column('questions', sa.Column('option_fingerprint', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_questions_option_fingerprint'), 'questions', ['option_fingerprint'], unique=False)
    op.create_index(op.f('ix_questions_stem_hash'), 'questions', ['stem_hash'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_questions_stem_hash'), table_name='questions')
    op.drop_index(op.f('ix_questions_option_fingerprint'), table_name='questions')
    op.drop_column('questions', 'option_fingerprint')
    op.drop_column('questions', 'stem_hash')
