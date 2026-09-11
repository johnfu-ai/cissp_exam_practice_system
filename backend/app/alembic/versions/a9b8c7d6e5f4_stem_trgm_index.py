"""pg_trgm GIN index on question_translations.stem

Perf item #5: the admin question search filters with a leading-wildcard
``stem ILIKE '%term%'`` (services/question.py::list_questions), which cannot
use a b-tree index and sequential-scans question_translations on every
search. A pg_trgm GIN index makes that shape index-backed.

Revision ID: a9b8c7d6e5f4
Revises: f1a2b3c4d5e6
Create Date: 2026-09-11

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a9b8c7d6e5f4"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extension creation needs appropriate privileges (superuser or the RDS
    # rds_superuser grant); it is a no-op when already installed.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_question_translations_stem_trgm "
        "ON question_translations USING gin (stem gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_question_translations_stem_trgm")
    # pg_trgm is intentionally left installed on downgrade: it is harmless,
    # shared across the database, and other objects may depend on it.
