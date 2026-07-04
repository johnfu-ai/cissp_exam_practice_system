"""unique constraints on answers

Revision ID: 2f0684f4fbb6
Revises: 6dad1bddd1d2
Create Date: 2026-07-04 08:53:50.272503
"""
from alembic import op
import sqlalchemy as sa


revision = '2f0684f4fbb6'
down_revision = '6dad1bddd1d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # DB-level backstop for the row-lock in _load_session(for_update=True):
    # a concurrent duplicate (session_id, question_id) insert raises
    # IntegrityError instead of corrupting the session (audit P1 #15).
    # `uq_users_email_lower` is the hand-written functional index filtered by
    # the no-drift test; not touched here despite the autogenerate flag.
    op.create_unique_constraint('uq_exam_answers_session_question', 'exam_answers', ['session_id', 'question_id'])
    op.create_unique_constraint('uq_practice_answers_session_question', 'practice_answers', ['session_id', 'question_id'])


def downgrade() -> None:
    op.drop_constraint('uq_practice_answers_session_question', 'practice_answers', type_='unique')
    op.drop_constraint('uq_exam_answers_session_question', 'exam_answers', type_='unique')
