"""add fk indexes

Revision ID: 6dad1bddd1d2
Revises: e7a1b2c3d4e5
Create Date: 2026-07-04 08:46:52.326069
"""
from alembic import op
import sqlalchemy as sa


revision = '6dad1bddd1d2'
down_revision = 'e7a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # B-tree indexes on high-traffic FK columns (audit P1 #12). The
    # `uq_users_email_lower` functional index is hand-written (not expressible
    # in column metadata) and is filtered by the no-drift test, so it is NOT
    # touched here despite alembic autogenerate flagging it.
    op.create_index('ix_audit_logs_actor_occurred', 'audit_logs', ['actor_id', 'occurred_at'], unique=False)
    op.create_index('ix_audit_logs_org_occurred', 'audit_logs', ['organization_id', 'occurred_at'], unique=False)
    op.create_index('ix_exam_answers_session_id', 'exam_answers', ['session_id'], unique=False)
    op.create_index('ix_exam_sessions_user_status', 'exam_sessions', ['user_id', 'status'], unique=False)
    op.create_index('ix_practice_answers_session_id', 'practice_answers', ['session_id'], unique=False)
    op.create_index('ix_practice_answers_user_question', 'practice_answers', ['user_id', 'question_id'], unique=False)
    op.create_index('ix_practice_sessions_user_status', 'practice_sessions', ['user_id', 'status'], unique=False)
    op.create_index('ix_question_feedback_question_id', 'question_feedback', ['question_id'], unique=False)
    op.create_index('ix_question_mappings_domain_id', 'question_mappings', ['domain_id'], unique=False)
    op.create_index('ix_question_mappings_question_id', 'question_mappings', ['question_id'], unique=False)
    op.create_index('ix_question_options_question_id', 'question_options', ['question_id'], unique=False)
    op.create_index('ix_question_revisions_question_id', 'question_revisions', ['question_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_question_revisions_question_id', table_name='question_revisions')
    op.drop_index('ix_question_options_question_id', table_name='question_options')
    op.drop_index('ix_question_mappings_question_id', table_name='question_mappings')
    op.drop_index('ix_question_mappings_domain_id', table_name='question_mappings')
    op.drop_index('ix_question_feedback_question_id', table_name='question_feedback')
    op.drop_index('ix_practice_sessions_user_status', table_name='practice_sessions')
    op.drop_index('ix_practice_answers_user_question', table_name='practice_answers')
    op.drop_index('ix_practice_answers_session_id', table_name='practice_answers')
    op.drop_index('ix_exam_sessions_user_status', table_name='exam_sessions')
    op.drop_index('ix_exam_answers_session_id', table_name='exam_answers')
    op.drop_index('ix_audit_logs_org_occurred', table_name='audit_logs')
    op.drop_index('ix_audit_logs_actor_occurred', table_name='audit_logs')
