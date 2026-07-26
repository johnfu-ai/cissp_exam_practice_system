import os

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

import app.models  # noqa: F401
from app.db.base import Base

ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
MIG_DB = "postgresql+psycopg://cissp:cissp@localhost:5432/cissp_migtest"


def _cfg() -> Config:
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", MIG_DB)
    return cfg


def _drift_diff(mig_engine):
    """The exact comparison the no-drift guard runs, including its filters."""
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
    return diff


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
    """A full base <-> head round-trip must leave the DB at head with a schema
    that exactly matches model metadata (no drift). Previously this test ran the
    round-trip on an empty DB and asserted nothing - so a broken/lossy downgrade
    that left the schema malformed would pass silently (#22)."""
    cfg = _cfg()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    head = ScriptDirectory.from_config(cfg).get_current_head()
    with mig_engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == head, f"expected head {head} after round-trip, got {version}"

    # The round-trip must have restored the exact head schema.
    diff = _drift_diff(mig_engine)
    assert diff == [], f"schema drift after base<->head round-trip: {diff}"


def test_no_autogenerate_drift(mig_engine):
    diff = _drift_diff(mig_engine)
    assert diff == [], f"Migration drift detected: {diff}"


def test_drift_guard_actually_detects_a_change(mig_engine):
    """Test-of-the-test (#22): prove the no-autogenerate-drift guard surfaces a
    real divergence. The real guard runs ``compare_metadata(ctx, Base.metadata)``;
    here we run the SAME comparison against a metadata holding a throwaway table
    that is NOT in the migrated DB, and assert it is reported. If
    compare_metadata ever silently tolerated a real model change, this test would
    fail. ``test_no_autogenerate_drift`` is the negative case (real metadata ->
    empty diff); together they prove the guard distinguishes clean from drifted.
    """
    from sqlalchemy import Column, MetaData, String, Table

    probe_meta = MetaData()
    Table("_drift_probe_xyz", probe_meta, Column("x", String(32)))
    with mig_engine.connect() as conn:
        ctx = MigrationContext.configure(
            conn, opts={"compare_type": True, "compare_server_default": True}
        )
        diff = list(compare_metadata(ctx, probe_meta))
    assert any(
        "_drift_probe_xyz" in str(d) for d in diff
    ), "drift guard failed to detect an unmodeled table; compare_metadata is toothless"
