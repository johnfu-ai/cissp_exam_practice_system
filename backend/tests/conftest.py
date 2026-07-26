import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

import app.models  # noqa: F401  -- registers all tables on Base.metadata
from app.db.base import Base

# Tests run against a dedicated, ephemeral database (NOT the dev DB) so committed
# seed data in the dev DB can never collide with test inserts. When the DB role
# has CREATEDB, the DB is dropped and recreated fresh each session and tables are
# built from model metadata. When the role lacks CREATEDB (e.g. an in-container
# or restricted CI runner), the suite falls back to a PRE-CREATED test DB whose
# schema is reset each session via drop_all/create_all - see _reset_schema.
TEST_DB_NAME = os.environ.get("TEST_DB_NAME", "cissp_test")
ADMIN_URL = os.environ.get(
    "TEST_ADMIN_URL",
    "postgresql+psycopg://cissp:cissp@localhost:5432/cissp",
)
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    f"postgresql+psycopg://cissp:cissp@localhost:5432/{TEST_DB_NAME}",
)


def _role_can_create_db() -> bool:
    """True iff the ADMIN_URL role has CREATEDB (or is a superuser). Picks the
    drop/create-DB path vs the pre-created-DB fallback. Any failure to even ask
    (admin DB unreachable) is treated as 'no CREATEDB' so the suite degrades to
    the fallback instead of hard-failing at import time."""
    admin = None
    try:
        admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            return bool(
                conn.execute(
                    text(
                        "SELECT rolcreatedb FROM pg_roles "
                        "WHERE rolname = current_user"
                    )
                ).scalar()
            )
    except Exception:
        return False
    finally:
        if admin is not None:
            admin.dispose()


def _drop_create_db() -> None:
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    admin.dispose()


def _drop_db() -> None:
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
    admin.dispose()


def _reset_schema(eng) -> None:
    """The no-CREATEDB fallback: drop and recreate every table on an existing
    (pre-created) test DB so each session starts from a clean schema. The test
    DB must already exist; if it doesn't, raise a clear, actionable error."""
    try:
        Base.metadata.drop_all(eng)
    except OperationalError as exc:
        raise RuntimeError(
            f"The test database '{TEST_DB_NAME}' does not exist and the DB role "
            f"connecting via {ADMIN_URL} lacks CREATEDB, so conftest cannot create "
            f"it. Pre-create it once with a privileged user, e.g.:\n"
            f"  psql -U postgres -c \"CREATE DATABASE {TEST_DB_NAME};\"\n"
            f"  psql -U postgres -c \"GRANT ALL ON DATABASE {TEST_DB_NAME} TO cissp;\""
        ) from exc
    Base.metadata.create_all(eng)


@pytest.fixture(scope="session")
def engine():
    can_create = _role_can_create_db()
    if can_create:
        _drop_create_db()
    eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, future=True)
    if can_create:
        Base.metadata.create_all(eng)
    else:
        # No CREATEDB: reset schema on the pre-created test DB (raises a clear
        # error if the operator forgot to pre-create it).
        _reset_schema(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()
    if can_create:
        _drop_db()


@pytest.fixture
def db_session(engine) -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    nested = connection.begin_nested()

    from sqlalchemy import event

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def session_with_roles(db_session):
    """db_session with seeded roles + permissions (individual_learner perms)."""
    from app.db.seed import PERMISSIONS, ROLE_PERMISSIONS
    from app.models.auth import Permission, Role, RolePermission
    from app.models.enums import RoleName

    perm_by_code = {}
    for code, desc in PERMISSIONS:
        p = db_session.query(Permission).filter_by(code=code).first()
        if p is None:
            p = Permission(code=code, description=desc)
            db_session.add(p)
            db_session.flush()
        perm_by_code[code] = p
    role_by_name = {}
    for name in RoleName:
        r = db_session.query(Role).filter_by(name=name).first()
        if r is None:
            r = Role(name=name, description=name.value)
            db_session.add(r)
            db_session.flush()
        role_by_name[name] = r
    for name, codes in ROLE_PERMISSIONS.items():
        for code in codes:
            exists = db_session.query(RolePermission).filter_by(
                role_id=role_by_name[name].id, permission_id=perm_by_code[code].id
            ).first()
            if exists is None:
                db_session.add(RolePermission(
                    role_id=role_by_name[name].id, permission_id=perm_by_code[code].id,
                ))
    db_session.flush()
    return db_session
