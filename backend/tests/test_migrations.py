import os

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

import app.models  # noqa: F401
from app.db.base import Base

ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
MIG_DB = "postgresql+psycopg://cissp:cissp@localhost:5432/cissp_migtest"


@pytest.fixture
def mig_engine():
    admin = create_engine(
        "postgresql+psycopg://cissp:cissp@localhost:5432/cissp",
        isolation_level="AUTOCOMMIT",
    )
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS cissp_migtest"))
        conn.execute(text("CREATE DATABASE cissp_migtest"))
    admin.dispose()

    eng = create_engine(MIG_DB)
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", MIG_DB)
    command.upgrade(cfg, "head")
    yield eng

    eng.dispose()
    admin = create_engine(
        "postgresql+psycopg://cissp:cissp@localhost:5432/cissp",
        isolation_level="AUTOCOMMIT",
    )
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS cissp_migtest"))
    admin.dispose()


def test_upgrade_then_downgrade_succeeds(mig_engine):
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", MIG_DB)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_no_autogenerate_drift(mig_engine):
    with mig_engine.connect() as conn:
        ctx = MigrationContext.configure(
            conn, opts={"compare_type": True, "compare_server_default": True}
        )
        diff = list(compare_metadata(ctx, Base.metadata))
    # Filter out the functional email index, which is intentionally hand-written
    # and not expressible in model metadata.
    diff = [d for d in diff if "uq_users_email_lower" not in str(d)]
    # Filter out throwaway test-only tables (e.g. _test_widgets in test_models)
    # that get registered into Base.metadata when the test module is imported.
    diff = [d for d in diff if not str(d).startswith("('add_table', Table('_test_")]
    assert diff == [], f"Migration drift detected: {diff}"
