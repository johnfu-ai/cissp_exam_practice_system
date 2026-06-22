"""add error_type to user_question_states

Revision ID: 145d056cbfbe
Revises: d8e1f2a3b4cd
Create Date: 2026-06-23 04:46:19.760419
"""
from alembic import op
import sqlalchemy as sa


revision = '145d056cbfbe'
down_revision = 'd8e1f2a3b4cd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Native PostgreSQL ENUM type must be created explicitly before the column
    # is added; op.add_column does not auto-create types the way op.create_table does.
    op.execute(
        "CREATE TYPE error_type AS ENUM "
        "('concept_unclear', 'misread_stem', 'memory_lapse', "
        "'option_confusion', 'time_pressure')"
    )
    op.add_column(
        'user_question_states',
        sa.Column(
            'error_type',
            sa.Enum(
                'concept_unclear',
                'misread_stem',
                'memory_lapse',
                'option_confusion',
                'time_pressure',
                name='error_type',
            ),
            nullable=True,
        ),
    )
    # NOTE: autogenerate also emitted `op.drop_index('uq_users_email_lower')` here.
    # That index is the hand-written functional email-uniqueness index (not
    # expressible in model metadata); the no-drift test filters it out. Dropping
    # it for real would break case-insensitive email uniqueness, so it is omitted.


def downgrade() -> None:
    op.drop_column('user_question_states', 'error_type')
    # Drop the enum type explicitly (autogen does not handle this).
    op.execute("DROP TYPE error_type")
