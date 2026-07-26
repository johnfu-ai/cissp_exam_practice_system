"""#21: the session engine fixture must not hard-require CREATEDB.

When the DB role lacks CREATEDB (e.g. an in-container or restricted CI runner
where the app DB user is not a superuser), conftest falls back to resetting the
schema on a PRE-CREATED test DB instead of drop/create-ing it per session.

This test simulates that fallback path: it provisions a throwaway DB with the
(superuser) test role to stand in for the operator pre-creating the test DB,
then exercises ``_reset_schema`` and verifies it yields a clean, working schema.
The throwaway DB is dropped afterwards. If the test role itself lacks CREATEDB
the test is skipped rather than failed.
"""
import pytest
from sqlalchemy import create_engine, func, inspect, select, text

import app.models  # noqa: F401  -- registers tables on Base.metadata
from app.db.base import Base
from app.models.auth import Organization

from tests.conftest import ADMIN_URL, TEST_DATABASE_URL, _reset_schema

PROBE_DB = "cissp_test_fallback_probe"


def test_reset_schema_produces_clean_working_schema():
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {PROBE_DB}"))
            c.execute(text(f"CREATE DATABASE {PROBE_DB}"))
    except Exception as exc:
        pytest.skip(f"cannot provision throwaway DB for fallback test: {exc}")
    finally:
        admin.dispose()

    url = TEST_DATABASE_URL.rsplit("/", 1)[0] + f"/{PROBE_DB}"
    eng = create_engine(url, pool_pre_ping=True, future=True)
    try:
        # The no-CREATEDB fallback: builds a clean schema on an existing DB.
        _reset_schema(eng)

        # A representative table exists...
        assert "organizations" in inspect(eng).get_table_names()
        # ...and starts empty (the schema was reset, not just left as-is).
        with eng.connect() as conn:
            count = conn.execute(
                select(func.count()).select_from(Organization)
            ).scalar()
        assert count == 0
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()
        admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {PROBE_DB}"))
        admin.dispose()
