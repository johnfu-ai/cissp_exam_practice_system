from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        # P2: explicit pool tuning (size/overflow/recycle) instead of psycopg
        # defaults; pool_recycle < Postgres idle timeout avoids reusing
        # server-closed connections (pool_pre_ping also catches this).
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_recycle=settings.db_pool_recycle,
        )
    return _engine


def get_sessionmaker() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


def get_session() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def dispose_engine() -> None:
    """Close the pooled DB connections. Called on app shutdown (Tier 2 #24
    graceful shutdown) so a SIGTERM/deploy doesn't leak pool connections."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionLocal = None
