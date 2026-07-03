"""password_reset + password_change audit actions

Revision ID: e7a1b2c3d4e5
Revises: 2668af3a57ef
Create Date: 2026-07-03

Adds two values to the native `audit_action` PostgreSQL enum so password
reset and password change events get a dedicated AuditAction (instead of
being folded into `config_change` with a `{"reset": True}` detail blob).
"""
from alembic import op


revision = "e7a1b2c3d4e5"
down_revision = "2668af3a57ef"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS keeps this idempotent across re-applies.
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'password_reset'")
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'password_change'")


def downgrade() -> None:
    # PostgreSQL has no safe DROP VALUE for enums (none pre-13; unsupported on
    # 13+). Removing enum values is unsafe and unnecessary for rollback
    # semantics — leaving them in place is harmless. Intentional no-op.
    pass
