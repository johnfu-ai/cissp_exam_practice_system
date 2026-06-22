"""question feedback table

Revision ID: 50a14663f11a
Revises: f9f9c63775fc
Create Date: 2026-06-22 22:57:22.508351
"""
from alembic import op
import sqlalchemy as sa


revision = '50a14663f11a'
down_revision = 'f9f9c63775fc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('question_feedback',
    sa.Column('question_id', sa.Uuid(), nullable=False),
    sa.Column('reporter_id', sa.Uuid(), nullable=True),
    sa.Column('feedback_type', sa.Enum('unclear_explanation', 'suspected_wrong_answer', 'ambiguous_stem', 'copyright_issue', 'other', name='question_feedback_type'), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('status', sa.Enum('open', 'resolved', 'wont_fix', name='question_feedback_status'), server_default='open', nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reporter_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # NOTE: autogenerate also emitted `op.drop_index('uq_users_email_lower')` here.
    # That index is the hand-written functional email-uniqueness index (not
    # expressible in model metadata); the no-drift test filters it out. Dropping
    # it for real would break case-insensitive email uniqueness, so it is omitted.


def downgrade() -> None:
    op.drop_table('question_feedback')
    # Drop the enum types explicitly (autogen does not handle this).
    sa.Enum(name='question_feedback_type').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='question_feedback_status').drop(op.get_bind(), checkfirst=False)
