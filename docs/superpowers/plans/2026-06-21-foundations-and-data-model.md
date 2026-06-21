# Foundations & Data Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a runnable full-stack scaffold (FastAPI + Next.js + Postgres + Redis) with all ~22 core data models, Alembic migrations, idempotent seed data, and a green test suite — the prerequisite for every later sub-project.

**Architecture:** Monorepo. Backend = FastAPI service-layer with SQLAlchemy 2.x `Base` + reusable mixins (timestamps, soft-delete, tenant-scoping, audit-subject) shared across domain-grouped model modules. Postgres-backed Alembic migrations + idempotent seed. Frontend = thin bootable Next.js placeholder hitting `/health`. Everything orchestrated via Docker Compose.

**Tech Stack:** Python 3.11 (Docker; local ≥3.11 ok), FastAPI, SQLAlchemy 2.0, Alembic, psycopg 3, pydantic-settings, redis-py, pytest. Node 20 (Docker; local ok), Next.js 14 App Router, TypeScript, Tailwind. PostgreSQL 16, Redis 7.

## Global Constraints

- **Repo is a git repo** (already `git init`'d; commit after each task).
- **Python packaging:** `pip` + `venv` + `requirements.txt`. No Poetry/uv.
- **Canonical runtime = Docker images** `python:3.11-slim` and `node:20-slim`. Local dev may use the system Python (3.14) / Node (24) — both ≥ the floors.
- **Primary keys:** UUID with `server_default=text("gen_random_uuid()")` on every table.
- **Enums:** native Postgres `ENUM` via `sqlalchemy.Enum(MyEnum, name="...", create_type=True)`. All enums live in `backend/app/models/enums.py`.
- **Timestamps:** timezone-aware UTC, `server_default=text("now()")`, `updated_at` `onupdate=text("now()")`.
- **Tenant scoping:** every *content* table has NOT NULL `organization_id` FK→`organizations.id`. Taxonomy tables (`ExamBlueprint`, `ExamDomain`, `KnowledgePoint`, `KnowledgePointDomain`, `Tag`) are global — no `organization_id`.
- **Soft delete:** `deleted_at` nullable; reads use the `not_deleted(model)` filter helper; `with_deleted` = omit the filter. Only the row itself is marked; children/snapshots untouched.
- **Test DB:** real Postgres (not SQLite). Tests use a transaction-rollback fixture; migration tests use a clean schema.
- **No business endpoints in this plan** — only `/health`. No auth, no import pipeline, no practice/exam logic, no background worker.
- **Model file layout:** one module per bounded context (`models/auth.py`, `taxonomy.py`, `question.py`, `practice.py`, `exam.py`, `admin.py`) + `enums.py`, all re-exported by `models/__init__.py`. (Refines the spec's "subpackages" to single modules — equivalent grouping, less ceremony.)
- **Commit message prefix:** `feat:` / `chore:` / `test:` / `docs:`.

---

## File Structure

```
backend/
├── Dockerfile
├── requirements.txt
├── pytest.ini
├── .env.example
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app factory + /health
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py            # Settings (pydantic-settings)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py              # Base + mixins
│   │   ├── session.py           # engine + get_session dependency
│   │   ├── queries.py           # not_deleted() soft-delete helper
│   │   └── seed.py              # run_seed(session) + __main__ CLI
│   ├── models/
│   │   ├── __init__.py          # registry: imports all contexts
│   │   ├── enums.py             # all enums
│   │   ├── auth.py              # Organization, User, Role, Permission, RolePermission, OrganizationMembership
│   │   ├── taxonomy.py          # ExamBlueprint, ExamDomain, KnowledgePoint, KnowledgePointDomain, Tag
│   │   ├── question.py          # Book, Chapter, Question, QuestionOption, Explanation, QuestionMapping, QuestionRevision, ImportJob
│   │   ├── practice.py          # PracticeSession, PracticeAnswer, UserQuestionState
│   │   ├── exam.py              # ExamSession, ExamAnswer
│   │   └── admin.py             # AuditLog, SchemaMeta
│   ├── services/
│   │   ├── __init__.py
│   │   ├── audit.py             # log_audit() helper
│   │   └── snapshot.py          # snapshot_question() helper
│   └── alembic/
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
│   alembic.ini                  # at backend/ root
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_models.py
│   ├── test_migrations.py
│   ├── test_seed.py
│   ├── test_snapshot.py
│   └── test_audit.py
frontend/
├── Dockerfile
├── package.json
├── next.config.mjs
├── tsconfig.json
├── tailwind.config.ts
├── postcss.config.js
└── src/
    └── app/
        ├── layout.tsx
        ├── page.tsx
        └── globals.css
docker-compose.yml
.gitignore
```

---

### Task 1: Repo scaffolding, Docker infra, backend skeleton

**Files:**
- Create: `.gitignore`
- Create: `docker-compose.yml`
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py` (empty)
- Create: `backend/app/core/__init__.py` (empty)
- Create: `backend/app/db/__init__.py` (empty)
- Create: `backend/app/models/__init__.py` (empty)
- Create: `backend/app/services/__init__.py` (empty)
- Create: `backend/tests/__init__.py` (empty)

**Interfaces:**
- Produces: running Postgres + Redis containers; a backend venv with all deps installed; `docker compose` working. Later tasks assume `docker compose up -d postgres redis` yields healthy services and that `cd backend && source venv/bin/activate` gives `python -m pytest`.

- [ ] **Step 1: Write `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
venv/
.venv/
.pytest_cache/
.coverage
htmlcov/

# Node
node_modules/
.next/
out/

# Env
.env
.env.local

# Editor
.vscode/
.idea/
*.swp

# OS
.DS_Store

# DB
*.sqlite3
```

- [ ] **Step 2: Write `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: cissp
      POSTGRES_USER: cissp
      POSTGRES_PASSWORD: cissp
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cissp"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  pgdata:
```

- [ ] **Step 3: Write `backend/requirements.txt`**

```
fastapi==0.115.4
uvicorn[standard]==0.32.0
sqlalchemy==2.0.36
alembic==1.13.3
psycopg[binary]==3.2.3
pydantic-settings==2.6.1
redis==5.2.0
httpx==0.27.2
pytest==8.3.3
```

- [ ] **Step 4: Write `backend/.env.example`**

```
APP_ENV=development
DATABASE_URL=postgresql+psycopg://cissp:cissp@localhost:5432/cissp
REDIS_URL=redis://localhost:6379/0
# JWT settings are placeholders; used in sub-project B.
JWT_SECRET=change-me
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

- [ ] **Step 5: Create empty package `__init__.py` files**

Create each of these as empty files:
- `backend/app/__init__.py`
- `backend/app/core/__init__.py`
- `backend/app/db/__init__.py`
- `backend/app/models/__init__.py`
- `backend/app/services/__init__.py`
- `backend/tests/__init__.py`

- [ ] **Step 6: Start infra and verify health**

Run:
```bash
docker compose up -d postgres redis
```
Wait, then verify:
```bash
docker compose ps
```
Expected: `postgres` and `redis` both show status `healthy` (or `Up`). If not healthy, run `docker compose logs postgres redis` to diagnose.

- [ ] **Step 7: Create backend venv and install deps**

Run:
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cd ..
```
Expected: all packages install without error.

- [ ] **Step 8: Commit**

```bash
git add .gitignore docker-compose.yml backend/
git commit -m "chore: repo scaffolding, docker infra, backend skeleton"
```

---

### Task 2: Backend config + FastAPI app + /health endpoint

**Files:**
- Create: `backend/app/core/config.py`
- Create: `backend/app/main.py`
- Create: `backend/pytest.ini`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

**Interfaces:**
- Consumes: Postgres + Redis from Task 1.
- Produces: `app.core.config.settings` (a `Settings` instance with `database_url`, `redis_url`, `app_env`); `app.main.app` (a FastAPI instance); `app.main.create_app()` factory. `GET /health` returns `{"status": "ok", "db": "ok", "redis": "ok"}`. The `conftest.py` exposes fixtures `engine` (sqlalchemy Engine bound to the test DB), `db_session` (Session with per-test rollback), and `client` (httpx AsyncClient / Starlette TestClient). Later tasks import `settings`, `engine`, and `db_session`.

- [ ] **Step 1: Write `backend/app/core/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://cissp:cissp@localhost:5432/cissp"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60


settings = Settings()
```

- [ ] **Step 2: Write `backend/app/main.py`**

```python
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_engine, get_session


def create_app() -> FastAPI:
    app = FastAPI(title="CISSP Exam Practice System", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        db_status = "ok"
        redis_status = "ok"
        try:
            engine = get_engine()
            with Session(engine) as session:
                session.execute(text("SELECT 1"))
        except Exception:
            db_status = "error"
        try:
            import redis

            r = redis.from_url(settings.redis_url, socket_connect_timeout=2)
            r.ping()
        except Exception:
            redis_status = "error"
        return {"status": "ok", "db": db_status, "redis": redis_status}

    return app


app = create_app()
```

- [ ] **Step 3: Write `backend/app/db/session.py`**

```python
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
        _engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
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
```

- [ ] **Step 4: Write `backend/pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -q
```

- [ ] **Step 5: Write the failing test `backend/tests/test_health.py`**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok_with_db_and_redis():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["redis"] == "ok"
```

- [ ] **Step 6: Write `backend/tests/conftest.py`**

```python
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Point tests at the dev DB (created by docker compose). Tests use a separate
# schema-stable DB; tables are created/dropped per session in Task 3+.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://cissp:cissp@localhost:5432/cissp",
)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, future=True)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine) -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    # Start a nested SAVEPOINT so per-test logic can rollback internally.
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
```

- [ ] **Step 7: Run the test to verify it passes**

Run (from `backend/`, venv active, `docker compose up -d postgres redis` running):
```bash
pytest tests/test_health.py -v
```
Expected: PASS. (If db/redis report "error", confirm containers are healthy and `DATABASE_URL`/`REDIS_URL` resolve to `localhost`.)

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/config.py backend/app/main.py backend/app/db/session.py backend/pytest.ini backend/tests/conftest.py backend/tests/test_health.py
git commit -m "feat: backend config, FastAPI app, /health endpoint"
```

---

### Task 3: DB Base + mixins + soft-delete helper

**Files:**
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/queries.py`
- Create: `backend/tests/test_models.py` (mixin portion)

**Interfaces:**
- Produces: `app.db.base.Base` (a `DeclarativeBase`); mixins `TimestampMixin`, `SoftDeleteMixin`, `TenantScopedMixin`, `AuditSubjectMixin`; a `Timestamped` convenience combining `TimestampMixin`. `app.db.queries.not_deleted(model)` returns a SQLAlchemy filter clause (`model.deleted_at.is_(None)`). All later model modules import `Base` and the mixins from here. **Important:** the `conftest.py` `engine` fixture must create all tables; this task extends `conftest` to call `Base.metadata.create_all` — but `Base` only knows about models that have been imported. Because models arrive in Tasks 4–8, the conftest will import `app.models` (the registry) which is populated by then. For THIS task's tests, a throwaway model is defined inside the test module to exercise the mixins without depending on later tasks.

- [ ] **Step 1: Write `backend/app/db/base.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid


class Base(DeclarativeBase):
    """Single declarative base for the whole app."""

    type_annotation_map = {uuid.UUID: Uuid}


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class TenantScopedMixin:
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )


class AuditSubjectMixin:
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
```

- [ ] **Step 2: Write `backend/app/db/queries.py`**

```python
"""Soft-delete query helpers.

Reads against soft-deletable models should scope with not_deleted(model).
To include soft-deleted rows (admin views), simply omit the filter.
"""

from sqlalchemy.orm import DeclarativeBase


def not_deleted(model: type[DeclarativeBase]):
    """Return a filter clause excluding soft-deleted rows.

    Raises AttributeError if the model lacks a deleted_at column, which surfaces
    misuse early rather than silently returning an unscoped query.
    """
    return model.deleted_at.is_(None)
```

- [ ] **Step 3: Write the failing test `backend/tests/test_models.py`**

```python
import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKey,
)
from app.db.queries import not_deleted


class _Widget(UUIDPrimaryKey, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "_test_widgets"
    name: Mapped[str] = mapped_column(nullable=False)


@pytest.fixture
def widget_table(engine):
    _Widget.__table__.create(engine, checkfirst=True)
    yield
    _Widget.__table__.drop(engine, checkfirst=True)


def test_timestamps_set_on_insert(db_session, widget_table):
    w = _Widget(name="alpha")
    db_session.add(w)
    db_session.flush()
    assert w.created_at is not None
    assert w.updated_at is not None
    assert w.id is not None and isinstance(w.id, uuid.UUID)


def test_soft_delete_default_none(db_session, widget_table):
    w = _Widget(name="beta")
    db_session.add(w)
    db_session.flush()
    assert w.deleted_at is None


def test_not_deleted_filter_excludes_soft_deleted(db_session, widget_table):
    live = _Widget(name="live")
    dead = _Widget(name="dead")
    dead.deleted_at = datetime.now()
    db_session.add_all([live, dead])
    db_session.flush()

    rows = db_session.execute(select(_Widget).where(not_deleted(_Widget))).scalars().all()
    names = {r.name for r in rows}
    assert names == {"live"}


def test_uuid_primary_key_default(db_session, widget_table):
    w = _Widget(name="gamma")
    db_session.add(w)
    db_session.flush()
    # gen_random_uuid() fired server-side; id is populated after refresh.
    db_session.refresh(w)
    assert isinstance(w.id, uuid.UUID)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/test_models.py -v
```
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/base.py backend/app/db/queries.py backend/tests/test_models.py
git commit -m "feat: db Base, mixins, soft-delete helper"
```

---

### Task 4: Enums + auth models

**Files:**
- Create: `backend/app/models/enums.py`
- Create: `backend/app/models/auth.py`
- Modify: `backend/app/models/__init__.py` (registry)
- Modify: `backend/tests/conftest.py` (create/drop all tables per session)
- Add tests to `backend/tests/test_models.py`

**Interfaces:**
- Produces: `Organization`, `User`, `Role`, `Permission`, `RolePermission`, `OrganizationMembership`. Enums `OrgKind` (`personal`, `institution`), `OrgStatus` (`active`, `disabled`), `UserStatus` (`active`, `disabled`), `RoleName` (`individual_learner`, `instructor`, `content_editor`, `org_admin`, `system_admin`). All later content models FK to `organizations.id` (via `TenantScopedMixin`) and `users.id` (via `AuditSubjectMixin`), so this task must land before any content model.

- [ ] **Step 1: Write `backend/app/models/enums.py`**

```python
import enum


class OrgKind(str, enum.Enum):
    personal = "personal"
    institution = "institution"


class OrgStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class RoleName(str, enum.Enum):
    individual_learner = "individual_learner"
    instructor = "instructor"
    content_editor = "content_editor"
    org_admin = "org_admin"
    system_admin = "system_admin"


class TextFormat(str, enum.Enum):
    plain = "plain"
    markdown = "markdown"


class QuestionType(str, enum.Enum):
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    true_false = "true_false"
    scenario = "scenario"
    ordering = "ordering"
    drag_drop = "drag_drop"
    hotspot = "hotspot"


class QuestionStatus(str, enum.Enum):
    draft = "draft"
    pending_review = "pending_review"
    published = "published"
    needs_revision = "needs_revision"
    archived = "archived"


class LicenseStatus(str, enum.Enum):
    user_owned = "user_owned"
    third_party_licensed = "third_party_licensed"
    public_domain = "public_domain"
    unconfirmed = "unconfirmed"


class ImportFormat(str, enum.Enum):
    csv = "csv"
    xlsx = "xlsx"
    json = "json"


class ImportStatus(str, enum.Enum):
    pending = "pending"
    validating = "validating"
    previewing = "previewing"
    importing = "importing"
    completed = "completed"
    failed = "failed"
    partial = "partial"


class PracticeSessionStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"
    abandoned = "abandoned"


class ExamSessionKind(str, enum.Enum):
    fixed = "fixed"
    cat = "cat"


class ExamSessionStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"
    aborted = "aborted"
    auto_submitted = "auto_submitted"


class MasteryLevel(str, enum.Enum):
    not_started = "not_started"
    learning = "learning"
    reviewing = "reviewing"
    mastered = "mastered"


class AuditAction(str, enum.Enum):
    login = "login"
    logout = "logout"
    import_action = "import"
    edit = "edit"
    publish = "publish"
    delete = "delete"
    archive = "archive"
    permission_change = "permission_change"
    config_change = "config_change"
```

- [ ] **Step 2: Write `backend/app/models/auth.py`**

```python
import uuid
from datetime import date

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey
from app.models.enums import OrgKind, OrgStatus, RoleName, UserStatus


class Organization(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("slug", name="uq_organizations_slug"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[OrgKind] = mapped_column(
        Enum(OrgKind, name="org_kind", create_type=True), nullable=False
    )
    status: Mapped[OrgStatus] = mapped_column(
        Enum(OrgStatus, name="org_status", create_type=True),
        nullable=False,
        server_default=OrgStatus.active.value,
    )


class User(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", create_type=True),
        nullable=False,
        server_default=UserStatus.active.value,
    )
    default_organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )


class Role(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("name", name="uq_roles_name"),)

    name: Mapped[RoleName] = mapped_column(
        Enum(RoleName, name="role_name", create_type=True), nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Permission(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("code", name="uq_permissions_code"),)

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)


class RolePermission(UUIDPrimaryKey, Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permissions"),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False
    )


class OrganizationMembership(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "organization_id", "role_id", name="uq_org_membership"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
```

- [ ] **Step 3: Update `backend/app/models/__init__.py` registry**

```python
"""Model registry. Importing this package registers all tables on Base.metadata
so Alembic autogenerate and Base.metadata.create_all see every table.
"""

from app.models.auth import (  # noqa: F401
    Organization,
    OrganizationMembership,
    Permission,
    Role,
    RolePermission,
    User,
)

__all__ = [
    "Organization",
    "User",
    "Role",
    "Permission",
    "RolePermission",
    "OrganizationMembership",
]
```

- [ ] **Step 4: Update `backend/tests/conftest.py` to create all tables**

Replace the `engine` fixture with one that creates/drops all registered tables. Add at the top of the file (after imports):

```python
import app.models  # noqa: F401  -- registers all tables on Base.metadata
from app.db.base import Base
```

Replace the `engine` fixture body:

```python
@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, future=True)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()
```

- [ ] **Step 5: Add failing tests to `backend/tests/test_models.py`**

```python
from app.models.auth import Organization, Role, User
from app.models.enums import OrgKind, RoleName


def test_organization_insert(db_session):
    org = Organization(name="Personal", slug="personal", kind=OrgKind.personal)
    db_session.add(org)
    db_session.flush()
    assert org.id is not None
    assert org.status.value == "active"


def test_user_email_case_insensitive_index_exists(engine):
    # The functional unique index on lower(email) is created in the migration
    # (Task 9), not via create_all. Here we only assert the column exists.
    cols = {c["name"] for c in engine.dialect.get_columns(engine, "users")}
    assert "email" in cols


def test_role_unique_name(db_session):
    r = Role(name=RoleName.system_admin, description="root")
    db_session.add(r)
    db_session.flush()
    assert r.id is not None
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_models.py -v
```
Expected: all PASS (the 4 mixin tests + 3 new auth tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/enums.py backend/app/models/auth.py backend/app/models/__init__.py backend/tests/conftest.py backend/tests/test_models.py
git commit -m "feat: enums + auth models (org, user, role, permission, membership)"
```

---

### Task 5: Taxonomy models

**Files:**
- Create: `backend/app/models/taxonomy.py`
- Modify: `backend/app/models/__init__.py`
- Add tests to `backend/tests/test_models.py`

**Interfaces:**
- Produces: `ExamBlueprint`, `ExamDomain`, `KnowledgePoint`, `KnowledgePointDomain`, `Tag`. These are GLOBAL (no `organization_id`). `ExamDomain` FKs `ExamBlueprint`. `KnowledgePoint` is self-referencing via `parent_id`. `KnowledgePointDomain` joins KPs to `ExamDomain`. Question models (Task 6) FK to `exam_domains.id` via `QuestionMapping`.

- [ ] **Step 1: Write `backend/app/models/taxonomy.py`**

```python
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey


class ExamBlueprint(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "exam_blueprints"
    __table_args__ = (
        UniqueConstraint("version_label", name="uq_blueprints_version_label"),
    )

    version_label: Mapped[str] = mapped_column(String(50), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    min_items: Mapped[int] = mapped_column(Integer, nullable=False)
    max_items: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    passing_score: Mapped[int] = mapped_column(Integer, nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )


class ExamDomain(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "exam_domains"
    __table_args__ = (
        UniqueConstraint("blueprint_id", "number", name="uq_domains_blueprint_number"),
    )

    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_blueprints.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    weight_pct: Mapped[int] = mapped_column(Integer, nullable=False)


class KnowledgePoint(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "knowledge_points"

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class KnowledgePointDomain(UUIDPrimaryKey, Base):
    __tablename__ = "knowledge_point_domains"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_point_id", "domain_id", name="uq_kp_domain"
        ),
    )

    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False
    )
    domain_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_domains.id", ondelete="CASCADE"), nullable=False
    )


class Tag(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("name", name="uq_tags_name"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

- [ ] **Step 2: Update `backend/app/models/__init__.py`**

Append taxonomy imports inside the existing file. Full replacement:

```python
"""Model registry. Importing this package registers all tables on Base.metadata
so Alembic autogenerate and Base.metadata.create_all see every table.
"""

from app.models.auth import (  # noqa: F401
    Organization,
    OrganizationMembership,
    Permission,
    Role,
    RolePermission,
    User,
)
from app.models.taxonomy import (  # noqa: F401
    ExamBlueprint,
    ExamDomain,
    KnowledgePoint,
    KnowledgePointDomain,
    Tag,
)

__all__ = [
    "Organization",
    "User",
    "Role",
    "Permission",
    "RolePermission",
    "OrganizationMembership",
    "ExamBlueprint",
    "ExamDomain",
    "KnowledgePoint",
    "KnowledgePointDomain",
    "Tag",
]
```

- [ ] **Step 3: Add failing tests to `backend/tests/test_models.py`**

```python
from app.models.taxonomy import ExamBlueprint, ExamDomain, KnowledgePoint


def test_blueprint_and_domain(db_session):
    bp = ExamBlueprint(
        version_label="2024-04-15",
        effective_date=date(2024, 4, 15),
        min_items=100,
        max_items=150,
        duration_minutes=180,
        passing_score=700,
        max_score=1000,
        is_current=True,
    )
    db_session.add(bp)
    db_session.flush()

    d1 = ExamDomain(blueprint_id=bp.id, number=1, name="Security and Risk Management", weight_pct=16)
    db_session.add(d1)
    db_session.flush()
    assert d1.id is not None
    assert d1.weight_pct == 16


def test_knowledge_point_self_reference(db_session):
    parent = KnowledgePoint(name="Cryptography")
    db_session.add(parent)
    db_session.flush()
    child = KnowledgePoint(name="Symmetric", parent_id=parent.id)
    db_session.add(child)
    db_session.flush()
    assert child.parent_id == parent.id
```

Add `from datetime import date` to the test imports if not already present.

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_models.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/taxonomy.py backend/app/models/__init__.py backend/tests/test_models.py
git commit -m "feat: taxonomy models (blueprint, domain, knowledge point, tag)"
```

---

### Task 6: Question models

**Files:**
- Create: `backend/app/models/question.py`
- Modify: `backend/app/models/__init__.py`
- Add tests to `backend/tests/test_models.py`

**Interfaces:**
- Produces: `Book`, `Chapter`, `Question`, `QuestionOption`, `Explanation`, `QuestionMapping`, `QuestionRevision`, `ImportJob`. All tenant-scoped (`organization_id`) except `ImportJob` (also tenant-scoped). `Question` uses `TenantScopedMixin` + `SoftDeleteMixin` + `AuditSubjectMixin` + `TimestampMixin`. `Question` FKs `import_job_id`→`import_jobs.id` (nullable). `QuestionMapping` FKs to `exam_domains`, `chapters`, `knowledge_points`, `tags` (all nullable). Practice/exam snapshot helper (Task 7) consumes `Question` + `QuestionOption`.

- [ ] **Step 1: Write `backend/app/models/question.py`**

```python
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    AuditSubjectMixin,
    Base,
    SoftDeleteMixin,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKey,
)
from app.models.enums import (
    ImportFormat,
    ImportStatus,
    LicenseStatus,
    QuestionStatus,
    QuestionType,
    TextFormat,
)


class ImportJob(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "import_jobs"

    format: Mapped[ImportFormat] = mapped_column(
        Enum(ImportFormat, name="import_format", create_type=True), nullable=False
    )
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    license_status: Mapped[LicenseStatus] = mapped_column(
        Enum(LicenseStatus, name="license_status", create_type=True),
        nullable=False,
        server_default=LicenseStatus.unconfirmed.value,
    )
    status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus, name="import_status", create_type=True),
        nullable=False,
        server_default=ImportStatus.pending.value,
    )
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    initiated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )


class Book(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "books"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    edition: Mapped[str | None] = mapped_column(String(100), nullable=True)
    author: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class Chapter(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "chapters"

    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)


class Question(
    UUIDPrimaryKey,
    TenantScopedMixin,
    TimestampMixin,
    SoftDeleteMixin,
    AuditSubjectMixin,
    Base,
):
    __tablename__ = "questions"

    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type", create_type=True), nullable=False
    )
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    stem_format: Mapped[TextFormat] = mapped_column(
        Enum(TextFormat, name="text_format", create_type=True),
        nullable=False,
        server_default=TextFormat.markdown.value,
    )
    difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str] = mapped_column(String(5), nullable=False, server_default=text("'en'"))
    status: Mapped[QuestionStatus] = mapped_column(
        Enum(QuestionStatus, name="question_status", create_type=True),
        nullable=False,
        server_default=QuestionStatus.draft.value,
    )
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    license_status: Mapped[LicenseStatus] = mapped_column(
        Enum(LicenseStatus, name="license_status", create_type=True),
        nullable=False,
        server_default=LicenseStatus.unconfirmed.value,
    )
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class QuestionOption(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "question_options"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_format: Mapped[TextFormat] = mapped_column(
        Enum(TextFormat, name="text_format", create_type=True),
        nullable=False,
        server_default=TextFormat.markdown.value,
    )
    is_correct: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)


class Explanation(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "explanations"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    correct_answer_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    key_point_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    further_reading: Mapped[str | None] = mapped_column(Text, nullable=True)


class QuestionMapping(UUIDPrimaryKey, Base):
    __tablename__ = "question_mappings"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    domain_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("exam_domains.id", ondelete="SET NULL"), nullable=True
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True
    )
    knowledge_point_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True
    )
    tag_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tags.id", ondelete="SET NULL"), nullable=True
    )


class QuestionRevision(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "question_revisions"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    edited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 2: Update `backend/app/models/__init__.py`**

Add question imports. Full replacement:

```python
"""Model registry. Importing this package registers all tables on Base.metadata
so Alembic autogenerate and Base.metadata.create_all see every table.
"""

from app.models.auth import (  # noqa: F401
    Organization,
    OrganizationMembership,
    Permission,
    Role,
    RolePermission,
    User,
)
from app.models.question import (  # noqa: F401
    Book,
    Chapter,
    Explanation,
    ImportJob,
    Question,
    QuestionMapping,
    QuestionOption,
    QuestionRevision,
)
from app.models.taxonomy import (  # noqa: F401
    ExamBlueprint,
    ExamDomain,
    KnowledgePoint,
    KnowledgePointDomain,
    Tag,
)

__all__ = [
    "Organization",
    "User",
    "Role",
    "Permission",
    "RolePermission",
    "OrganizationMembership",
    "ExamBlueprint",
    "ExamDomain",
    "KnowledgePoint",
    "KnowledgePointDomain",
    "Tag",
    "Book",
    "Chapter",
    "Question",
    "QuestionOption",
    "Explanation",
    "QuestionMapping",
    "QuestionRevision",
    "ImportJob",
]
```

- [ ] **Step 3: Add failing tests to `backend/tests/test_models.py`**

```python
from app.models.auth import Organization
from app.models.enums import OrgKind, QuestionStatus, QuestionType
from app.models.question import Question, QuestionOption


def _make_org(db_session):
    org = Organization(name="Acme", slug="acme", kind=OrgKind.institution)
    db_session.add(org)
    db_session.flush()
    return org


def test_question_tenant_scoped_and_soft_delete(db_session):
    org = _make_org(db_session)
    q = Question(
        organization_id=org.id,
        question_type=QuestionType.single_choice,
        stem="What is CIA?",
        stem_format="markdown",
    )
    db_session.add(q)
    db_session.flush()
    assert q.organization_id == org.id
    assert q.status.value == "draft"
    assert q.license_status.value == "unconfirmed"
    assert q.version == 1
    assert q.deleted_at is None
    assert q.created_by_id is None  # AuditSubjectMixin present, nullable


def test_question_option(db_session):
    org = _make_org(db_session)
    q = Question(
        organization_id=org.id,
        question_type=QuestionType.multiple_choice,
        stem="Pick two",
    )
    db_session.add(q)
    db_session.flush()
    opt = QuestionOption(
        question_id=q.id, order_index=0, content="Option A", is_correct=True
    )
    db_session.add(opt)
    db_session.flush()
    assert opt.is_correct is True
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_models.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/question.py backend/app/models/__init__.py backend/tests/test_models.py
git commit -m "feat: question models (book, chapter, question, option, explanation, mapping, revision, import_job)"
```

---

### Task 7: Practice + exam models + snapshot helper

**Files:**
- Create: `backend/app/models/practice.py`
- Create: `backend/app/models/exam.py`
- Create: `backend/app/services/snapshot.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/tests/test_snapshot.py`
- Add tests to `backend/tests/test_models.py`

**Interfaces:**
- Produces: `PracticeSession`, `PracticeAnswer`, `UserQuestionState` (practice.py); `ExamSession`, `ExamAnswer` (exam.py). `PracticeAnswer`/`ExamAnswer` carry `question_snapshot` + `options_snapshot` (JSONB). `app.services.snapshot.snapshot_question(question, options) -> dict` builds the frozen representation consumed by answer rows. All session/answer tables are tenant-scoped + user-owned (`user_id` FK→users.id).

- [ ] **Step 1: Write `backend/app/services/snapshot.py`**

```python
"""Snapshot producer for historical answer integrity (NFR-DATA-01).

Captures a frozen, minimal representation of a question and its options at
answer time so later edits never alter historical records. The blob lives in
JSONB and may evolve its internal shape without a migration.
"""

import uuid
from typing import Any

from app.models.question import Question, QuestionOption


def snapshot_question(question: Question, options: list[QuestionOption]) -> dict[str, Any]:
    return {
        "question_id": str(question.id),
        "question_type": question.question_type.value,
        "stem": question.stem,
        "stem_format": question.stem_format.value,
        "difficulty": question.difficulty,
        "language": question.language,
        "version": question.version,
        "options": [
            {
                "order_index": o.order_index,
                "content": o.content,
                "content_format": o.content_format.value,
                "is_correct": o.is_correct,
            }
            for o in sorted(options, key=lambda o: o.order_index)
        ],
    }
```

- [ ] **Step 2: Write `backend/app/models/practice.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKey
from app.models.enums import MasteryLevel, PracticeSessionStatus


class PracticeSession(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "practice_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[PracticeSessionStatus] = mapped_column(
        Enum(PracticeSessionStatus, name="practice_session_status", create_type=True),
        nullable=False,
        server_default=PracticeSessionStatus.in_progress.value,
    )
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PracticeAnswer(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "practice_answers"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), nullable=False)
    question_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    options_snapshot: Mapped[list] = mapped_column(JSONB, nullable=False)
    user_answer: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(nullable=True)
    time_spent_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class UserQuestionState(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "user_question_states"
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_user_question_state"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), nullable=False)
    is_bookmarked: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    is_flagged_review: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    is_mastered: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    is_questioned: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    mastery_level: Mapped[MasteryLevel] = mapped_column(
        Enum(MasteryLevel, name="mastery_level", create_type=True),
        nullable=False,
        server_default=MasteryLevel.not_started.value,
    )
```

- [ ] **Step 3: Write `backend/app/models/exam.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKey
from app.models.enums import ExamSessionKind, ExamSessionStatus


class ExamSession(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "exam_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_blueprints.id"), nullable=False
    )
    session_kind: Mapped[ExamSessionKind] = mapped_column(
        Enum(ExamSessionKind, name="exam_session_kind", create_type=True), nullable=False
    )
    status: Mapped[ExamSessionStatus] = mapped_column(
        Enum(ExamSessionStatus, name="exam_session_status", create_type=True),
        nullable=False,
        server_default=ExamSessionStatus.in_progress.value,
    )
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExamAnswer(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "exam_answers"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), nullable=False)
    question_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    options_snapshot: Mapped[list] = mapped_column(JSONB, nullable=False)
    user_answer: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(nullable=True)
    time_spent_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ability_estimate_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    se_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
```

- [ ] **Step 4: Update `backend/app/models/__init__.py`**

Add practice + exam imports. Full replacement:

```python
"""Model registry. Importing this package registers all tables on Base.metadata
so Alembic autogenerate and Base.metadata.create_all see every table.
"""

from app.models.auth import (  # noqa: F401
    Organization,
    OrganizationMembership,
    Permission,
    Role,
    RolePermission,
    User,
)
from app.models.exam import ExamAnswer, ExamSession  # noqa: F401
from app.models.practice import (  # noqa: F401
    PracticeAnswer,
    PracticeSession,
    UserQuestionState,
)
from app.models.question import (  # noqa: F401
    Book,
    Chapter,
    Explanation,
    ImportJob,
    Question,
    QuestionMapping,
    QuestionOption,
    QuestionRevision,
)
from app.models.taxonomy import (  # noqa: F401
    ExamBlueprint,
    ExamDomain,
    KnowledgePoint,
    KnowledgePointDomain,
    Tag,
)

__all__ = [
    "Organization",
    "User",
    "Role",
    "Permission",
    "RolePermission",
    "OrganizationMembership",
    "ExamBlueprint",
    "ExamDomain",
    "KnowledgePoint",
    "KnowledgePointDomain",
    "Tag",
    "Book",
    "Chapter",
    "Question",
    "QuestionOption",
    "Explanation",
    "QuestionMapping",
    "QuestionRevision",
    "ImportJob",
    "PracticeSession",
    "PracticeAnswer",
    "UserQuestionState",
    "ExamSession",
    "ExamAnswer",
]
```

- [ ] **Step 5: Write failing test `backend/tests/test_snapshot.py`**

```python
from app.models.enums import OrgKind, QuestionType
from app.models.auth import Organization
from app.models.question import Question, QuestionOption
from app.services.snapshot import snapshot_question


def test_snapshot_question_round_trips_through_jsonb(db_session):
    org = Organization(name="Acme", slug="acme", kind=OrgKind.institution)
    db_session.add(org)
    db_session.flush()

    q = Question(
        organization_id=org.id,
        question_type=QuestionType.single_choice,
        stem="What is 2+2?",
        difficulty=2,
        language="en",
        version=1,
    )
    db_session.add(q)
    db_session.flush()

    opts = [
        QuestionOption(question_id=q.id, order_index=0, content="3", is_correct=False),
        QuestionOption(question_id=q.id, order_index=1, content="4", is_correct=True),
    ]
    db_session.add_all(opts)
    db_session.flush()

    snap = snapshot_question(q, opts)
    assert snap["question_type"] == "single_choice"
    assert snap["stem"] == "What is 2+2?"
    assert len(snap["options"]) == 2
    assert snap["options"][0]["content"] == "3"
    assert snap["options"][1]["is_correct"] is True

    # Round-trip: store in a PracticeAnswer and read back.
    from app.models.auth import User
    from app.models.enums import UserStatus
    from app.models.practice import PracticeAnswer, PracticeSession

    user = User(email="a@b.com", status=UserStatus.active, default_organization_id=org.id)
    db_session.add(user)
    db_session.flush()
    sess = PracticeSession(organization_id=org.id, user_id=user.id, total_questions=1)
    db_session.add(sess)
    db_session.flush()

    pa = PracticeAnswer(
        session_id=sess.id,
        user_id=user.id,
        question_id=q.id,
        question_snapshot=snap,
        options_snapshot=snap["options"],
        user_answer={"indices": [1]},
        is_correct=True,
    )
    db_session.add(pa)
    db_session.flush()
    db_session.refresh(pa)

    assert pa.question_snapshot["options"][1]["is_correct"] is True
    assert pa.options_snapshot[0]["content"] == "3"
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_snapshot.py tests/test_models.py -v
```
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/practice.py backend/app/models/exam.py backend/app/services/snapshot.py backend/app/models/__init__.py backend/tests/test_snapshot.py backend/tests/test_models.py
git commit -m "feat: practice + exam models, snapshot helper for historical integrity"
```

---

### Task 8: Admin models + log_audit helper

**Files:**
- Create: `backend/app/models/admin.py`
- Create: `backend/app/services/audit.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/tests/test_audit.py`

**Interfaces:**
- Produces: `AuditLog`, `SchemaMeta`. `app.services.audit.log_audit(session, *, action, actor_id=None, organization_id=None, entity_type=None, entity_id=None, details=None, ip_address=None)` inserts an `AuditLog` row. `SchemaMeta` is a simple key/value table (`key` unique). Seed (Task 10) uses `SchemaMeta` to store `seed_version`.

- [ ] **Step 1: Write `backend/app/models/admin.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey
from app.models.enums import AuditAction


class AuditLog(UUIDPrimaryKey, Base):
    __tablename__ = "audit_logs"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action", create_type=True), nullable=False
    )
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class SchemaMeta(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "schema_meta"
    __table_args__ = ({"schema": None},)  # default schema; keep simple

    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    value: Mapped[str | None] = mapped_column(String(1000), nullable=True)
```

Note: remove the empty `__table_args__` tuple on `SchemaMeta` if it causes issues — it's a no-op placeholder; safer to simply omit it. **Use this version instead:**

```python
class SchemaMeta(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "schema_meta"

    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    value: Mapped[str | None] = mapped_column(String(1000), nullable=True)
```

- [ ] **Step 2: Write `backend/app/services/audit.py`**

```python
"""Audit logging helper (NFR-DATA-05 / FR-ADMIN-06).

Writes a single AuditLog row. The session is NOT committed here; callers control
the transaction. Sub-projects call this from real actions (B/C onward).
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.admin import AuditLog
from app.models.enums import AuditAction


def log_audit(
    session: Session,
    *,
    action: AuditAction,
    actor_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        organization_id=organization_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address,
    )
    session.add(entry)
    session.flush()
    return entry
```

- [ ] **Step 3: Update `backend/app/models/__init__.py`**

Add admin imports. Append:

```python
from app.models.admin import AuditLog, SchemaMeta  # noqa: F401
```
and add `"AuditLog", "SchemaMeta"` to `__all__`.

- [ ] **Step 4: Write failing test `backend/tests/test_audit.py`**

```python
from app.models.admin import AuditLog, SchemaMeta
from app.models.enums import AuditAction
from app.services.audit import log_audit


def test_log_audit_inserts_row(db_session):
    entry = log_audit(
        db_session,
        action=AuditAction.publish,
        entity_type="question",
        entity_id="abc-123",
        details={"from": "draft", "to": "published"},
    )
    db_session.flush()
    db_session.refresh(entry)
    assert entry.id is not None
    assert entry.action == AuditAction.publish
    assert entry.details["to"] == "published"
    assert entry.occurred_at is not None


def test_schema_meta_key_value(db_session):
    m = SchemaMeta(key="seed_version", value="1")
    db_session.add(m)
    db_session.flush()
    db_session.refresh(m)
    assert m.key == "seed_version"
    assert m.value == "1"
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_audit.py -v
```
Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/admin.py backend/app/services/audit.py backend/app/models/__init__.py backend/tests/test_audit.py
git commit -m "feat: admin models (audit_log, schema_meta) + log_audit helper"
```

---

### Task 9: Alembic setup + initial migration + migration tests

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/app/alembic/env.py`
- Create: `backend/app/alembic/script.py.mako`
- Create: `backend/app/alembic/versions/` (directory)
- Create: `backend/tests/test_migrations.py`

**Interfaces:**
- Produces: a working Alembic config with `target_metadata = Base.metadata`; one initial revision creating all ~22 tables, ENUMs, UUID PKs, FKs, and the indexes listed in the spec; `alembic upgrade head` / `alembic downgrade base` both succeed on a clean DB; autogenerate reports no drift against current models.

- [ ] **Step 1: Write `backend/alembic.ini`**

```ini
[alembic]
script_location = app/alembic
prepend_sys_path = .
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Write `backend/app/alembic/env.py`**

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
import app.models  # noqa: F401  -- registers all tables
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Write `backend/app/alembic/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: Generate the initial migration (autogenerate)**

From `backend/` with venv active and Postgres running:
```bash
alembic revision --autogenerate -m "initial schema"
```
This creates `app/alembic/versions/<hash>_initial_schema.py`.

- [ ] **Step 5: Hand-fix the generated migration**

Open the generated file. Verify/fix these known autogenerate weak spots:

1. **ENUM types must be created before tables that use them, and dropped after.** Alembic usually handles this, but confirm each `sa.Enum(..., name="...", create_type=True)` is present and that no table's column references an enum type before its `sa.Enum(...).create()` call in `upgrade()`. Reorder if needed.

2. **Add the case-insensitive email unique index.** Autogenerate will produce a plain unique index on `users.email`; replace/augment it with a functional index. In `upgrade()`, ensure:
```python
op.execute(
    "CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email))"
)
```
Remove any conflicting plain unique constraint on `users.email` that autogenerate added (we did not declare `unique=True` on the column, so there should be none — but check).

3. **Confirm `gen_random_uuid()` server defaults** are present on every `id` column (they should be, from the models).

4. **Confirm FK `ondelete` behaviors** match the models (CASCADE / SET NULL).

In `downgrade()`, ensure `op.drop_index("uq_users_email_lower")` is present and tables/enums drop in reverse dependency order.

- [ ] **Step 6: Test upgrade/downgrade on a clean DB**

Create a throwaway clean database, run the migration up and down:
```bash
docker compose exec postgres psql -U cissp -c "DROP DATABASE IF EXISTS cissp_migtest;"
docker compose exec postgres psql -U cissp -c "CREATE DATABASE cissp_migtest;"
DATABASE_URL=postgresql+psycopg://cissp:cissp@localhost:5432/cissp_migtest alembic upgrade head
DATABASE_URL=postgresql+psycopg://cissp:cissp@localhost:5432/cissp_migtest alembic downgrade base
docker compose exec postgres psql -U cissp -c "DROP DATABASE cissp_migtest;"
```
Expected: both commands succeed with no errors.

- [ ] **Step 7: Write failing test `backend/tests/test_migrations.py`**

```python
import os

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import create_engine

import app.models  # noqa: F401
from app.db.base import Base

ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
MIG_DB = "postgresql+psycopg://cissp:cissp@localhost:5432/cissp_migtest"


@pytest.fixture
def mig_engine():
    # Ensure clean DB
    admin = create_engine("postgresql+psycopg://cissp:cissp@localhost:5432/cissp")
    with admin.connect() as conn:
        conn.exec_driver_sql("DROP DATABASE IF EXISTS cissp_migtest")
        conn.exec_driver_sql("CREATE DATABASE cissp_migtest")
    admin.dispose()

    eng = create_engine(MIG_DB)
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", MIG_DB)
    command.upgrade(cfg, "head")
    yield eng

    eng.dispose()
    admin = create_engine("postgresql+psycopg://cissp:cissp@localhost:5432/cissp")
    with admin.connect() as conn:
        conn.exec_driver_sql("DROP DATABASE IF EXISTS cissp_migtest")
    admin.dispose()


def test_upgrade_then_downgrade_succeeds(mig_engine):
    # If we got here, upgrade worked. Now test downgrade.
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", MIG_DB)
    command.downgrade(cfg, "base")
    # Re-upgrade to leave DB usable / confirm idempotent cycle.
    command.upgrade(cfg, "head")


def test_no_autogenerate_drift(mig_engine):
    with mig_engine.connect() as conn:
        ctx = MigrationContext.configure(
            conn, opts={"compare_type": True, "compare_server_default": True}
        )
        diff = list(compare_metadata(ctx, Base.metadata))
    # Filter out the functional email index, which is intentionally hand-written
    # and not expressible in model metadata.
    diff = [
        d for d in diff
        if not (len(d) > 1 and "uq_users_email_lower" in str(d))
    ]
    assert diff == [], f"Migration drift detected: {diff}"
```

- [ ] **Step 8: Run migration tests**

```bash
pytest tests/test_migrations.py -v
```
Expected: 2 PASS. If drift is reported, reconcile by editing the migration file (preferred) or the model so they match, then re-run until green.

- [ ] **Step 9: Commit**

```bash
git add backend/alembic.ini backend/app/alembic/ backend/tests/test_migrations.py
git commit -m "feat: alembic setup, initial schema migration, migration tests"
```

---

### Task 10: Seed logic + seed CLI + seed tests

**Files:**
- Create: `backend/app/db/seed.py`
- Create: `backend/tests/test_seed.py`

**Interfaces:**
- Produces: `app.db.seed.run_seed(session) -> dict` (idempotent; returns counts) and a `python -m app.db.seed` CLI that creates its own session. Seeds: 1 `personal` org, 1 current `2024-04-15` blueprint, 8 `ExamDomain` rows (weights 16/10/13/13/13/12/13/10), 5 `Role` rows, base `Permission` + `RolePermission` matrix, and a `SchemaMeta(seed_version="1")` marker. Re-running is a no-op (upserts).

- [ ] **Step 1: Write `backend/app/db/seed.py`**

```python
"""Idempotent system-reference seed.

Run via `python -m app.db.seed` or call run_seed(session). Re-running upserts;
guarded by SchemaMeta.seed_version.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin import SchemaMeta
from app.models.auth import Organization, Role
from app.models.enums import OrgKind, RoleName
from app.models.taxonomy import ExamBlueprint, ExamDomain

SEED_VERSION = "1"

# PRD §2 — CISSP 2024-04-15 blueprint weights.
DOMAINS = [
    (1, "Security and Risk Management", 16),
    (2, "Asset Security", 10),
    (3, "Security Architecture and Engineering", 13),
    (4, "Communication and Network Security", 13),
    (5, "Identity and Access Management (IAM)", 13),
    (6, "Security Assessment and Testing", 12),
    (7, "Security Operations", 13),
    (8, "Software Development Security", 10),
]

# Base permission codes. Enforcing endpoints arrive in sub-projects B-H.
PERMISSIONS = [
    ("question:read", "Read questions"),
    ("question:write", "Create/edit questions"),
    ("question:publish", "Publish/archive questions"),
    ("question:import", "Import question batches"),
    ("practice:read", "Start/view practice sessions"),
    ("exam:read", "Start/view exams"),
    ("admin:manage_users", "Manage users and roles"),
    ("admin:manage_taxonomy", "Manage exam config and taxonomy"),
    ("admin:view_audit", "View audit logs"),
]

# Role -> permission codes. system_admin gets everything.
ROLE_PERMISSIONS = {
    RoleName.individual_learner: ["question:read", "practice:read", "exam:read"],
    RoleName.instructor: ["question:read", "practice:read", "exam:read", "admin:manage_users"],
    RoleName.content_editor: ["question:read", "question:write", "question:publish", "question:import"],
    RoleName.org_admin: [
        "question:read", "question:write", "question:publish", "question:import",
        "practice:read", "exam:read", "admin:manage_users", "admin:view_audit",
    ],
    RoleName.system_admin: [code for code, _ in PERMISSIONS],
}


def _get_or_create(session, model, defaults=None, **filters):
    obj = session.execute(select(model).filter_by(**filters)).scalar_one_or_none()
    if obj is None:
        params = {**filters}
        if defaults:
            params.update(defaults)
        obj = model(**params)
        session.add(obj)
        session.flush()
    return obj


def run_seed(session: Session) -> dict:
    from app.models.auth import Permission, RolePermission

    counts = {"organizations": 0, "blueprints": 0, "domains": 0, "roles": 0, "permissions": 0}

    # Organization: the built-in personal org.
    org = _get_or_create(
        session,
        Organization,
        slug="personal",
        defaults={"name": "Personal", "kind": OrgKind.personal},
    )
    counts["organizations"] = 1

    # Exam blueprint.
    bp = _get_or_create(
        session,
        ExamBlueprint,
        version_label="2024-04-15",
        defaults={
            "effective_date": date(2024, 4, 15),
            "min_items": 100,
            "max_items": 150,
            "duration_minutes": 180,
            "passing_score": 700,
            "max_score": 1000,
            "is_current": True,
        },
    )
    counts["blueprints"] = 1

    # Domains.
    for number, name, weight in DOMAINS:
        _get_or_create(
            session,
            ExamDomain,
            blueprint_id=bp.id,
            number=number,
            defaults={"name": name, "weight_pct": weight},
        )
    counts["domains"] = len(DOMAINS)

    # Permissions.
    perm_by_code = {}
    for code, desc in PERMISSIONS:
        perm_by_code[code] = _get_or_create(
            session, Permission, code=code, defaults={"description": desc}
        )
    counts["permissions"] = len(PERMISSIONS)

    # Roles + role_permissions.
    role_by_name = {}
    for role_name in RoleName:
        role_by_name[role_name] = _get_or_create(
            session, Role, name=role_name, defaults={"description": role_name.value}
        )
    counts["roles"] = len(RoleName)

    for role_name, codes in ROLE_PERMISSIONS.items():
        role = role_by_name[role_name]
        for code in codes:
            perm = perm_by_code[code]
            existing = session.execute(
                select(RolePermission).filter_by(role_id=role.id, permission_id=perm.id)
            ).scalar_one_or_none()
            if existing is None:
                session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    session.flush()

    # Seed version marker.
    _get_or_create(session, SchemaMeta, key="seed_version", defaults={"value": SEED_VERSION})

    return counts


def main() -> None:
    from app.db.session import get_sessionmaker

    session = get_sessionmaker()()
    try:
        result = run_seed(session)
        session.commit()
        print(f"Seed complete: {result}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write failing test `backend/tests/test_seed.py`**

```python
from sqlalchemy import func, select

from app.db.seed import run_seed
from app.models.admin import SchemaMeta
from app.models.auth import Organization, Permission, Role, RolePermission
from app.models.enums import RoleName
from app.models.taxonomy import ExamBlueprint, ExamDomain


def test_seed_creates_expected_reference_data(db_session):
    result = run_seed(db_session)
    assert result["organizations"] == 1
    assert result["blueprints"] == 1
    assert result["domains"] == 8
    assert result["roles"] == 5

    org = db_session.execute(select(Organization).filter_by(slug="personal")).scalar_one()
    assert org.kind.value == "personal"

    bp = db_session.execute(
        select(ExamBlueprint).filter_by(version_label="2024-04-15")
    ).scalar_one()
    assert bp.is_current is True
    assert bp.min_items == 100 and bp.max_items == 150
    assert bp.duration_minutes == 180
    assert bp.passing_score == 700 and bp.max_score == 1000

    total_weight = db_session.execute(
        select(func.coalesce(func.sum(ExamDomain.weight_pct), 0)).where(
            ExamDomain.blueprint_id == bp.id
        )
    ).scalar_one()
    assert total_weight == 100

    role_count = db_session.execute(select(func.count()).select_from(Role)).scalar_one()
    assert role_count == 5


def test_seed_is_idempotent(db_session):
    run_seed(db_session)
    counts_1_perm = db_session.execute(
        select(func.count()).select_from(Permission)
    ).scalar_one()
    counts_1_rp = db_session.execute(
        select(func.count()).select_from(RolePermission)
    ).scalar_one()

    run_seed(db_session)  # second run

    counts_2_perm = db_session.execute(
        select(func.count()).select_from(Permission)
    ).scalar_one()
    counts_2_rp = db_session.execute(
        select(func.count()).select_from(RolePermission)
    ).scalar_one()

    assert counts_1_perm == counts_2_perm
    assert counts_1_rp == counts_2_rp

    sv = db_session.execute(select(SchemaMeta).filter_by(key="seed_version")).scalar_one()
    assert sv.value == "1"


def test_system_admin_has_all_permissions(db_session):
    run_seed(db_session)
    admin_role = db_session.execute(
        select(Role).filter_by(name=RoleName.system_admin)
    ).scalar_one()
    rp_count = db_session.execute(
        select(func.count()).select_from(RolePermission).where(
            RolePermission.role_id == admin_role.id
        )
    ).scalar_one()
    perm_total = db_session.execute(
        select(func.count()).select_from(Permission)
    ).scalar_one()
    assert rp_count == perm_total
```

- [ ] **Step 3: Run seed tests**

```bash
pytest tests/test_seed.py -v
```
Expected: 3 PASS.

- [ ] **Step 4: Run seed against the dev DB (manual smoke)**

```bash
cd backend
source venv/bin/activate
python -m app.db.seed
```
Expected: prints `Seed complete: {...}`. Re-run to confirm idempotency (counts unchanged, no duplicate-key errors).

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/seed.py backend/tests/test_seed.py
git commit -m "feat: idempotent seed (org, blueprint, 8 domains, roles, permissions)"
```

---

### Task 11: Frontend placeholder + health integration

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/next.config.mjs`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/page.tsx`
- Create: `frontend/src/app/globals.css`
- Create: `frontend/Dockerfile`

**Interfaces:**
- Produces: a bootable Next.js 14 App Router app. The home page (`/`) fetches `GET /health` from the backend and renders the status. `npm run build` succeeds. Backend URL is configurable via `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

- [ ] **Step 1: Write `frontend/package.json`**

```json
{
  "name": "cissp-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.2.15",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "@types/node": "20.14.0",
    "@types/react": "18.3.3",
    "@types/react-dom": "18.3.0",
    "autoprefixer": "10.4.20",
    "postcss": "8.4.47",
    "tailwindcss": "3.4.13",
    "typescript": "5.5.4"
  }
}
```

- [ ] **Step 2: Write `frontend/next.config.mjs`**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {};
export default nextConfig;
```

- [ ] **Step 3: Write `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 4: Write `frontend/tailwind.config.ts`**

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
export default config;
```

- [ ] **Step 5: Write `frontend/postcss.config.js`**

```javascript
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 6: Write `frontend/src/app/globals.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 7: Write `frontend/src/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CISSP Exam Practice System",
  description: "CISSP exam preparation platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900">{children}</body>
    </html>
  );
}
```

- [ ] **Step 8: Write `frontend/src/app/page.tsx`**

```tsx
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Health = { status: string; db: string; redis: string };

async function getHealth(): Promise<Health> {
  try {
    const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return { status: "unreachable", db: "unknown", redis: "unknown" };
  }
}

export default async function Home() {
  const health = await getHealth();
  const ok = health.status === "ok";
  return (
    <main className="mx-auto max-w-xl p-8">
      <h1 className="text-2xl font-bold">CISSP Exam Practice System</h1>
      <p className="mt-2 text-gray-600">Sub-project A — foundations & data model.</p>
      <div className="mt-6 rounded-lg border p-4">
        <p>
          Backend:{" "}
          <span className={ok ? "text-green-600 font-semibold" : "text-red-600 font-semibold"}>
            {health.status}
          </span>
        </p>
        <p>Database: {health.db}</p>
        <p>Redis: {health.redis}</p>
      </div>
    </main>
  );
}
```

- [ ] **Step 9: Write `frontend/Dockerfile`**

```dockerfile
FROM node:20-slim
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
CMD ["npm", "run", "dev"]
```

- [ ] **Step 10: Install deps and build**

```bash
cd frontend
npm install
npm run build
cd ..
```
Expected: `npm run build` succeeds (✓ Compiled successfully).

- [ ] **Step 11: Commit**

```bash
git add frontend/
git commit -m "feat: next.js placeholder frontend with health integration"
```

---

### Task 12: Dockerize backend + full `docker compose up` smoke

**Files:**
- Create: `backend/Dockerfile`
- Modify: `docker-compose.yml` (add `backend` + `frontend` services)

**Interfaces:**
- Produces: `docker compose up` brings all four services (postgres, redis, backend, frontend) healthy; `curl localhost:8000/health` returns `{"status":"ok","db":"ok","redis":"ok"}`; `curl localhost:3000` returns the page HTML.

- [ ] **Step 1: Write `backend/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Update `docker-compose.yml`**

Full replacement — adds `backend` and `frontend` services:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: cissp
      POSTGRES_USER: cissp
      POSTGRES_PASSWORD: cissp
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cissp"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      APP_ENV: development
      DATABASE_URL: postgresql+psycopg://cissp:cissp@postgres:5432/cissp
      REDIS_URL: redis://redis:6379/0
      JWT_SECRET: change-me
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    depends_on:
      - backend

volumes:
  pgdata:
```

- [ ] **Step 3: Add a `.dockerignore` to avoid copying venv/node_modules into images**

Create `backend/.dockerignore`:
```
venv/
__pycache__/
*.pyc
.pytest_cache/
.env
```
Create `frontend/.dockerignore`:
```
node_modules/
.next/
```

- [ ] **Step 4: Bring up the full stack**

```bash
docker compose up -d --build
docker compose ps
```
Expected: all four services `Up`/`healthy`.

- [ ] **Step 5: Run migrations + seed inside the backend container**

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.db.seed
```
Expected: both succeed; seed prints `Seed complete: {...}`.

- [ ] **Step 6: Smoke-test the endpoints**

```bash
curl -s localhost:8000/health
curl -s localhost:3000 | grep -o "CISSP Exam Practice System"
```
Expected: `{"status":"ok","db":"ok","redis":"ok"}` and the heading string respectively.

- [ ] **Step 7: Commit**

```bash
git add backend/Dockerfile backend/.dockerignore frontend/.dockerignore docker-compose.yml
git commit -m "feat: dockerize backend + frontend, full compose stack"
```

---

### Task 13: Update CLAUDE.md + final acceptance

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Produces: `CLAUDE.md` reflecting the now-real layout and working commands; the full acceptance criteria from spec §7 verified green.

- [ ] **Step 1: Update the "Current State" section of `CLAUDE.md`**

Replace the pre-code caveat with a real-state description. Change the opening to note the backend + frontend scaffolding now exists, Docker Compose brings up the full stack, and the commands below are live. Specifically:

- Remove/replace the "This repository is pre-code" paragraph.
- Note that sub-project A (foundations & data model) is implemented: ~22 models, Alembic migrations, seed, `/health`, tests green.
- Confirm the Backend/Frontend/Docker command blocks are now real and tested.

- [ ] **Step 2: Run the full backend test suite**

```bash
cd backend && source venv/bin/activate && pytest -v && cd ..
```
Expected: all tests PASS (health, models, snapshot, audit, migrations, seed).

- [ ] **Step 3: Run the frontend build**

```bash
cd frontend && npm run build && cd ..
```
Expected: ✓ Compiled successfully.

- [ ] **Step 4: Verify acceptance criteria checklist**

Confirm each spec §7 item:
1. git repo initialized + committed (done throughout).
2. `docker compose up` — all four healthy (Task 12).
3. `alembic upgrade head` / `downgrade base` clean (Task 9).
4. `python -m app.db.seed` idempotent (Task 10).
5. `pytest` green (Step 2).
6. `npm run build` succeeds (Step 3).
7. `CLAUDE.md` updated (Step 1).

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md to reflect implemented foundations (sub-project A)"
```

---

## Self-Review

**1. Spec coverage:**
- §2.1 repo layout → Task 1 + all file paths match.
- §2.2 stack/versions → Global Constraints + `requirements.txt` (T1), Dockerfiles (T12), `package.json` (T11).
- §2.3 tooling defaults (pip/venv, .env+Settings, no worker, no business schemas) → honored throughout; no Celery/Arq introduced.
- §2.4 thin frontend → Task 11.
- §3.1 Base + 4 mixins + UUID PKs + native ENUMs → Task 3 (base) + enums T4.
- §3.2 all model contexts (auth, taxonomy, question, practice, exam, admin) → Tasks 4–8.
- §3.3 snapshots (`snapshot_question`) + soft-delete behavior → Task 7 (snapshot) + Task 3 (soft-delete helper/tests).
- §3.4 out-of-scope items → none implemented (no auth endpoints, no import logic, no CAT, no analytics, no worker).
- §4 migrations (single env, initial revision, ENUMs, UUID defaults, indexes incl. lower(email)) → Task 9 (hand-fix step explicitly adds the email index).
- §5 seeding (personal org, 2024-04-15 blueprint, 8 domains w/ exact weights, 5 roles, permissions+matrix, idempotent, SchemaMeta guard) → Task 10.
- §6 testing (model/migration-no-drift/seed + health smoke; Postgres-backed; frontend build) → Tasks 2,3,4,5,6,7,8,9,10 + T11 build + T12 smoke.
- §7 done criteria → Task 13 maps each.
- §8 risks (autogenerate nuances, snapshot design, over-modeling) → mitigated by no-drift test (T9), JSONB blob producer (T7), accepted shell tables (T6 ImportJob/T7 ExamSession).

No spec gap found.

**2. Placeholder scan:** Searched for TBD/TODO/"implement later"/"add appropriate". One intentional placeholder remains: in Task 8 Step 1, the `SchemaMeta` model is shown twice — the second (simpler) version is the one to use; the instruction explicitly says to use the second. That is a directive, not a placeholder. No unfinished steps.

**3. Type consistency:**
- `not_deleted(model)` defined T3, used in T3 tests. ✓
- `snapshot_question(question, options)` signature defined T7, matches usage in test. ✓
- `log_audit(session, *, action, ...)` defined T8, matches test call. ✓
- `run_seed(session) -> dict` defined T10, returns `counts` dict consumed by tests. ✓
- Mixin names (`TimestampMixin`, `SoftDeleteMixin`, `TenantScopedMixin`, `AuditSubjectMixin`, `UUIDPrimaryKey`) consistent across T3 and every model task. ✓
- Enum names consistent: `OrgKind`, `OrgStatus`, `UserStatus`, `RoleName`, `QuestionType`, `QuestionStatus`, `LicenseStatus`, `ImportFormat`, `ImportStatus`, `PracticeSessionStatus`, `ExamSessionKind`, `ExamSessionStatus`, `MasteryLevel`, `AuditAction`, `TextFormat` — referenced identically in models and tests. ✓
- `conftest` fixtures `engine`/`db_session` defined T2, extended T4 (create_all), used by all model/snapshot/audit/seed tests. ✓

No type drift found.
