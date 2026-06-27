"""interface_language

Revision ID: 2668af3a57ef
Revises: a1b2c3d4e5f6
Create Date: 2026-06-27 15:38:04.300605
"""
from alembic import op
import sqlalchemy as sa


revision = '2668af3a57ef'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('interface_language', sa.String(length=16), server_default=sa.text("'en'"), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'interface_language')
