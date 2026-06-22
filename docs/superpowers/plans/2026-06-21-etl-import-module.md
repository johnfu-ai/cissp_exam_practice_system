# ETL Import Module (osg10) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the ETL pipeline that ingests `docs/questions/osg10/` (420 questions → 840 bilingual rows) idempotently into the question bank, driven by a CLI and an HTTP API, so the application runs with real question data.

**Architecture:** A four-phase pipeline under `app/etl/` — `extract.py` (file → `RawQuestion` dataclasses, pure I/O), `transform.py` (pure functions, `RawQuestion` → per-language `CleanedQuestion`), `load.py` (DB create-or-update + dedup by external key, savepoint-per-record), `runner.py` (orchestrates the dry-run/commit two-phase lifecycle and writes `EtlRun`/`ImportJob`). Dry-run runs extract+transform and persists a read-only summary; commit **re-runs** extract+transform (deterministic, idempotent) and applies the load in one transaction. A CLI (`python -m app.etl.cli`) and an unauthenticated FastAPI router (`/api/etl`) drive it.

**Tech Stack:** FastAPI, SQLAlchemy 2.x (`DeclarativeBase`+mixins), Alembic, PostgreSQL 16 (native ENUMs, JSONB, `gen_random_uuid()`), Pydantic, pytest.

## Global Constraints

Copied verbatim from the spec (`docs/superpowers/specs/2026-06-21-etl-import-module-design.md`) and PRD cross-cutting rules:

- **Service-layer backend**: API routes delegate to `runner.*` service functions; no business logic in route handlers.
- **Tenant scoping**: `EtlDataset`/`EtlRun` are org-scoped (`organization_id` NOT NULL); `QuestionExternalKey`/`ChapterDomainMapping` are GLOBAL (no `organization_id`).
- **Native PostgreSQL ENUMs**: `EtlRunPhase` created as `CREATE TYPE`; the migration's `downgrade()` explicitly `DROP TYPE`.
- **UUID PKs** via `gen_random_uuid()` server default (from `UUIDPrimaryKey` mixin).
- **Historical integrity**: updates write a `QuestionRevision` with the OLD snapshot via `snapshot_question()` before changing the row; bump `version`.
- **Soft delete only**: load never hard-deletes questions.
- **Audit logging**: `log_audit(session, action=AuditAction.import_action, ...)` on commit.
- **License safety**: `license_status` stays `unconfirmed`; imported questions enter as `draft`/`needs_revision`, never auto-published.
- **Idempotency**: unique key `(dataset_slug, external_id, language)`; re-runs update only changed rows.
- **Bilingual**: two `Question` rows per source (`language='en'` and `'zh'`).
- **matching → single_choice** + `prompt_items` JSONB; no enum change.
- **Tests** use the real `cissp_test` Postgres DB with per-test SAVEPOINT rollback (no SQLite). Migration no-drift test must stay green.
- `multiple_choice` validation requires **≥2** correct keys (PRD FR-ETL-06); `single_choice` exactly 1.

---

## File Structure

**Create:**
- `backend/app/models/etl.py` — `EtlDataset`, `EtlRun`, `QuestionExternalKey`, `ChapterDomainMapping` ORM models.
- `backend/app/etl/__init__.py` — package marker.
- `backend/app/etl/extract.py` — `RawQuestion` dataclasses + `DatasetReader`.
- `backend/app/etl/transform.py` — `CleanedQuestion` dataclass + `validate()`/`transform()` pure functions.
- `backend/app/etl/load.py` — `LoadResult`/`DryRunSummary` + `apply_load()`/`apply_dry_run()`.
- `backend/app/etl/runner.py` — `run_preview()`/`run_commit()`/`run_rollback()` + `EtlDriftError`.
- `backend/app/etl/cli.py` — `python -m app.etl.cli` entrypoint.
- `backend/app/api/etl.py` — FastAPI router mounted at `/api/etl`.
- `backend/app/alembic/versions/<new>_etl_models_and_prompt_items.py` — migration.
- `backend/tests/etl/__init__.py`
- `backend/tests/etl/fixtures/mini/manifest.json`, `backend/tests/etl/fixtures/mini/questions.jsonl`
- `backend/tests/etl/test_extract.py`, `test_transform.py`, `test_load.py`, `test_runner.py`, `test_api_etl.py`

**Modify:**
- `backend/app/models/enums.py` — add `EtlRunPhase`.
- `backend/app/models/question.py` — add `Question.prompt_items` JSONB.
- `backend/app/models/__init__.py` — register etl models.
- `backend/app/main.py` — mount `/api/etl` router.
- `backend/app/db/seed.py` — seed osg10 dataset + 21 chapter→domain mappings, bump `SEED_VERSION`.
- `backend/tests/test_seed.py` — assert osg10 seed rows.

---

### Task 1: New enum `EtlRunPhase`

**Files:**
- Modify: `backend/app/models/enums.py` (append after `ImportStatus`)

**Interfaces:**
- Consumes: nothing.
- Produces: `EtlRunPhase` enum (`preview`/`committed`/`rolled_back`) used by Task 2's `EtlRun.phase` column.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/etl/__init__.py` (empty) and `backend/tests/test_etl_enum.py`:

```python
from app.models.enums import EtlRunPhase


def test_etl_run_phase_values():
    assert EtlRunPhase.preview.value == "preview"
    assert EtlRunPhase.committed.value == "committed"
    assert EtlRunPhase.rolled_back.value == "rolled_back"
    assert EtlRunPhase("preview") is EtlRunPhase.preview
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_etl_enum.py -v`
Expected: FAIL with `ImportError: cannot import name 'EtlRunPhase'`

- [ ] **Step 3: Write minimal implementation**

Append to `backend/app/models/enums.py` after the `ImportStatus` class:

```python
class EtlRunPhase(str, enum.Enum):
    preview = "preview"
    committed = "committed"
    rolled_back = "rolled_back"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_etl_enum.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/enums.py backend/tests/etl/__init__.py backend/tests/test_etl_enum.py
git commit -m "feat(etl): add EtlRunPhase enum"
```

---

### Task 2: ETL ORM models

**Files:**
- Create: `backend/app/models/etl.py`
- Modify: `backend/app/models/question.py` (add `prompt_items` column)
- Modify: `backend/app/models/__init__.py` (register new models)
- Test: `backend/tests/etl/test_models.py`

**Interfaces:**
- Consumes: `EtlRunPhase` (Task 1), `Base`/mixins (`app.db.base`), `ImportFormat`/`ImportJob`/`ExamDomain`.
- Produces: `EtlDataset`, `EtlRun`, `QuestionExternalKey`, `ChapterDomainMapping` models; `Question.prompt_items` JSONB column.

- [ ] **Step 1: Write the failing test**

`backend/tests/etl/test_models.py`:

```python
import pytest
from sqlalchemy import inspect

from app.models.etl import (
    ChapterDomainMapping,
    EtlDataset,
    EtlRun,
    QuestionExternalKey,
)
from app.models.question import Question


def test_question_has_prompt_items_column():
    cols = {c["name"] for c in inspect(Question).columns}
    assert "prompt_items" in cols


def test_etl_dataset_columns():
    cols = {c["name"] for c in inspect(EtlDataset).columns}
    for name in [
        "id", "organization_id", "slug", "name", "source_path",
        "format", "total_questions", "languages", "notes",
        "created_at", "updated_at",
    ]:
        assert name in cols


def test_etl_run_columns():
    cols = {c["name"] for c in inspect(EtlRun).columns}
    for name in [
        "id", "organization_id", "dataset_id", "import_job_id",
        "phase", "preview_summary", "committed_at", "created_at", "updated_at",
    ]:
        assert name in cols


def test_question_external_key_is_global_and_unique():
    # GLOBAL = no organization_id column
    cols = {c["name"] for c in inspect(QuestionExternalKey).columns}
    assert "organization_id" not in cols
    for name in ["id", "dataset_slug", "external_id", "language", "question_id"]:
        assert name in cols


def test_chapter_domain_mapping_is_global():
    cols = {c["name"] for c in inspect(ChapterDomainMapping).columns}
    assert "organization_id" not in cols
    for name in ["id", "dataset_slug", "chapter_number", "domain_id", "chapter_title"]:
        assert name in cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/etl/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.etl'`

- [ ] **Step 3: Write `backend/app/models/etl.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKey,
)
from app.models.enums import EtlRunPhase, ImportFormat


class EtlDataset(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "etl_datasets"
    __table_args__ = (UniqueConstraint("slug", name="uq_etl_datasets_slug"),)

    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str] = mapped_column(String(500), nullable=False)
    format: Mapped[ImportFormat] = mapped_column(
        Enum(ImportFormat, name="import_format", create_type=False), nullable=False
    )
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    languages: Mapped[list[str]] = mapped_column(ARRAY(String(5)), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class EtlRun(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "etl_runs"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("etl_datasets.id"), nullable=False
    )
    import_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_jobs.id"), nullable=False
    )
    phase: Mapped[EtlRunPhase] = mapped_column(
        Enum(EtlRunPhase, name="etl_run_phase", create_type=True), nullable=False
    )
    preview_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class QuestionExternalKey(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "question_external_keys"
    __table_args__ = (
        UniqueConstraint(
            "dataset_slug", "external_id", "language", name="uq_qek_dataset_ext_lang"
        ),
    )

    dataset_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    language: Mapped[str] = mapped_column(String(5), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )


class ChapterDomainMapping(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "chapter_domain_mappings"
    __table_args__ = (
        UniqueConstraint(
            "dataset_slug", "chapter_number", name="uq_cdm_dataset_chapter"
        ),
    )

    dataset_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    domain_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("exam_domains.id", ondelete="SET NULL"), nullable=True
    )
    chapter_title: Mapped[str] = mapped_column(String(500), nullable=False)
```

Note: `EtlDataset.format` reuses the existing `import_format` PG enum (`create_type=False` so the migration does not try to recreate it). `EtlRun.phase` creates the new `etl_run_phase` type.

- [ ] **Step 4: Add `prompt_items` to `Question`**

In `backend/app/models/question.py`, add the import of `JSONB` is already present. Add this column inside the `Question` class (after `version`):

```python
    prompt_items: Mapped[list | None] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 5: Register models in `backend/app/models/__init__.py`**

Add after the `question` import block:

```python
from app.models.etl import (  # noqa: F401
    ChapterDomainMapping,
    EtlDataset,
    EtlRun,
    QuestionExternalKey,
)
```

And extend `__all__` with `"EtlDataset"`, `"EtlRun"`, `"QuestionExternalKey"`, `"ChapterDomainMapping"`.

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/etl/test_models.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/etl.py backend/app/models/question.py backend/app/models/__init__.py backend/tests/etl/test_models.py
git commit -m "feat(etl): add ETL ORM models + Question.prompt_items JSONB"
```

---

### Task 3: Alembic migration for ETL models

**Files:**
- Create: `backend/app/alembic/versions/<new>_etl_models_and_prompt_items.py`
- Test: `backend/tests/test_migrations.py` (existing — must stay green)

**Interfaces:**
- Consumes: models from Task 2.
- Produces: a migration revision with `down_revision = '66bec070d8fc'` that creates 4 tables + `etl_run_phase` type + `questions.prompt_items` column, with a reversible `downgrade()`.

- [ ] **Step 1: Autogenerate the migration**

Run:
```bash
cd backend && alembic revision --autogenerate -m "etl models and prompt_items"
```
This creates a new file under `app/alembic/versions/`. Open it.

- [ ] **Step 2: Verify and fix the generated migration**

Confirm the generated file:
- `down_revision = '66bec070d8fc'`
- `upgrade()` creates `etl_datasets`, `etl_runs`, `question_external_keys`, `chapter_domain_mappings` tables, creates the `etl_run_phase` type (via the `Enum(... create_type=True)` column), and does `op.add_column('questions', sa.Column('prompt_items', postgresql.JSONB(), nullable=True))`.
- The `etl_datasets.format` column must reference the EXISTING `import_format` type — confirm the generated code uses `sa.Enum(..., name='import_format', create_type=False)` (autogen may emit `create_type=True`; if so, change it to `False` so it does not try to recreate the existing type).
- `downgrade()` must `drop_column`, `drop_table` for all four tables AND explicitly drop the enum type:
  ```python
  etl_run_phase = sa.Enum(name='etl_run_phase')
  etl_run_phase.drop(op.get_bind(), checkfirst=False)
  ```
  Do NOT drop `import_format` (it is shared with `import_jobs`).

If autogen emitted anything that does not match the models exactly, do NOT hand-edit the table definitions — instead fix the model in Task 2 and regenerate. The drift test will catch mismatches.

- [ ] **Step 3: Verify no-autogenerate drift**

Run: `cd backend && python -m pytest tests/test_migrations.py -v`
Expected: PASS (both `test_upgrade_then_downgrade_succeeds` and `test_no_autogenerate_drift`).

- [ ] **Step 4: Commit**

```bash
git add backend/app/alembic/versions/
git commit -m "feat(etl): migration for ETL models and prompt_items"
```

---

### Task 4: Extract module

**Files:**
- Create: `backend/app/etl/__init__.py`
- Create: `backend/app/etl/extract.py`
- Create: `backend/tests/etl/fixtures/mini/manifest.json`
- Create: `backend/tests/etl/fixtures/mini/questions.jsonl`
- Test: `backend/tests/etl/test_extract.py`

**Interfaces:**
- Consumes: nothing (pure file I/O).
- Produces: `RawQuestion`/`RawSource`/`RawOption`/`RawPromptItem`/`Bilingual`/`ExtractError` dataclasses; `DatasetReader(path).read() -> tuple[list[RawQuestion], list[ExtractError], str]` (str = content hash).

- [ ] **Step 1: Create the fixture dataset**

`backend/tests/etl/fixtures/mini/manifest.json`:
```json
{
  "source": "test/mini",
  "total_questions": 3,
  "chapters": 2,
  "type_counts": {"single_choice": 1, "multiple_choice": 1, "matching": 1}
}
```

`backend/tests/etl/fixtures/mini/questions.jsonl` (3 lines, one per line — single_choice, multiple_choice, matching, plus a 4th malformed line):
```jsonl
{"id":"mini-ch01-q01","source":{"book":"Mini","edition":1,"section":"review","chapter":1,"chapter_title":"Chapter One","number":1},"type":"single_choice","stem":{"en":"Single?","zh":"单选？"},"options":[{"key":"A","text":{"en":"Yes","zh":"是"}},{"key":"B","text":{"en":"No","zh":"否"}}],"correct_keys":["A"],"explanation":{"en":"Yes is right.","zh":"是对的。"},"meta":{"choose_all":false,"matching":false,"issues":[],"zh_source":"v9","zh_issues":[]}}
{"id":"mini-ch01-q02","source":{"book":"Mini","edition":1,"section":"review","chapter":1,"chapter_title":"Chapter One","number":2},"type":"multiple_choice","stem":{"en":"Multi?","zh":"多选？"},"options":[{"key":"A","text":{"en":"A","zh":"甲"}},{"key":"B","text":{"en":"B","zh":"乙"}}],"correct_keys":["A","B"],"explanation":{"en":"Both.","zh":"都是。"},"meta":{"choose_all":true,"matching":false,"issues":[],"zh_source":"v9","zh_issues":[]}}
{"id":"mini-ch02-q01","source":{"book":"Mini","edition":1,"section":"review","chapter":2,"chapter_title":"Chapter Two","number":1},"type":"matching","stem":{"en":"Match.","zh":"匹配。"},"options":[{"key":"A","text":{"en":"1-I","zh":"1-I"}},{"key":"B","text":{"en":"2-II","zh":"2-II"}}],"correct_keys":["B"],"explanation":{"en":"B.","zh":"B。"},"meta":{"choose_all":false,"matching":true,"issues":[],"zh_source":"v9_aligned","zh_issues":[]},"prompt_items":[{"key":"1","text":{"en":"First","zh":"第一"}},{"key":"I","text":{"en":"One","zh":"一"}}]}
{not valid json
```

- [ ] **Step 2: Write the failing test**

`backend/tests/etl/test_extract.py`:
```python
from pathlib import Path

from app.etl.extract import DatasetReader, ExtractError, RawQuestion

FIXTURE = Path(__file__).parent / "fixtures" / "mini"


def test_read_returns_raws_and_errors():
    raws, errors, content_hash = DatasetReader(FIXTURE).read()
    assert len(raws) == 3
    assert len(errors) == 1
    assert isinstance(errors[0], ExtractError)
    assert errors[0].line_no == 4


def test_raw_question_types_and_bilingual():
    raws, _, _ = DatasetReader(FIXTURE).read()
    single = next(r for r in raws if r.id == "mini-ch01-q01")
    assert single.type == "single_choice"
    assert single.stem.en == "Single?"
    assert single.stem.zh == "单选？"
    assert single.options[0].key == "A"
    assert single.options[0].text.zh == "是"
    assert single.correct_keys == ["A"]


def test_matching_record_has_prompt_items():
    raws, _, _ = DatasetReader(FIXTURE).read()
    match = next(r for r in raws if r.id == "mini-ch02-q01")
    assert match.type == "matching"
    assert match.prompt_items is not None
    assert match.prompt_items[0].key == "1"
    assert match.prompt_items[0].text.zh == "第一"


def test_content_hash_stable():
    _, _, h1 = DatasetReader(FIXTURE).read()
    _, _, h2 = DatasetReader(FIXTURE).read()
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/etl/test_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.etl'`

- [ ] **Step 4: Write `backend/app/etl/__init__.py`** (empty file)

- [ ] **Step 5: Write `backend/app/etl/extract.py`**

```python
"""ETL Extract: read a dataset directory into RawQuestion dataclasses.

Pure file I/O + parsing. No DB, no business logic.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Bilingual:
    en: str
    zh: str


@dataclass
class RawSource:
    book: str
    edition: int
    section: str
    chapter: int
    chapter_title: str
    number: int


@dataclass
class RawOption:
    key: str
    text: Bilingual


@dataclass
class RawPromptItem:
    key: str
    text: Bilingual


@dataclass
class RawQuestion:
    id: str
    source: RawSource
    type: str
    stem: Bilingual
    options: list[RawOption]
    correct_keys: list[str]
    explanation: Bilingual
    meta: dict
    prompt_items: list[RawPromptItem] | None = None


@dataclass
class ExtractError:
    line_no: int | None
    external_id: str | None
    reason: str


def _bilingual(d: dict) -> Bilingual:
    return Bilingual(en=d.get("en", ""), zh=d.get("zh", ""))


def _parse_record(rec: dict) -> RawQuestion:
    src = rec["source"]
    raw = RawQuestion(
        id=rec["id"],
        source=RawSource(
            book=src["book"],
            edition=src["edition"],
            section=src["section"],
            chapter=src["chapter"],
            chapter_title=src["chapter_title"],
            number=src["number"],
        ),
        type=rec["type"],
        stem=_bilingual(rec["stem"]),
        options=[
            RawOption(key=o["key"], text=_bilingual(o["text"]))
            for o in rec["options"]
        ],
        correct_keys=list(rec["correct_keys"]),
        explanation=_bilingual(rec["explanation"]),
        meta=rec.get("meta", {}),
        prompt_items=(
            [
                RawPromptItem(key=p["key"], text=_bilingual(p["text"]))
                for p in rec["prompt_items"]
            ]
            if rec.get("prompt_items")
            else None
        ),
    )
    return raw


class DatasetReader:
    def __init__(self, dataset_path: str | Path):
        self.path = Path(dataset_path)

    def read(self) -> tuple[list[RawQuestion], list[ExtractError], str]:
        raws: list[RawQuestion] = []
        errors: list[ExtractError] = []
        content_hash = self._content_hash()

        manifest = json.loads((self.path / "manifest.json").read_text())
        expected = manifest.get("total_questions")

        jsonl = self.path / "questions.jsonl"
        with jsonl.open() as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    raws.append(_parse_record(rec))
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    external_id = rec.get("id") if isinstance(rec, dict) else None
                    errors.append(
                        ExtractError(
                            line_no=line_no,
                            external_id=external_id,
                            reason=f"{type(exc).__name__}: {exc}",
                        )
                    )

        if expected is not None and expected != len(raws):
            errors.append(
                ExtractError(
                    line_no=None,
                    external_id=None,
                    reason=f"manifest total_questions={expected} but parsed {len(raws)} records",
                )
            )

        return raws, errors, content_hash

    def _content_hash(self) -> str:
        h = hashlib.sha256()
        for name in ("manifest.json", "questions.jsonl"):
            h.update(name.encode())
            h.update((self.path / name).read_bytes())
        return h.hexdigest()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/etl/test_extract.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/etl/__init__.py backend/app/etl/extract.py backend/tests/etl/fixtures/ backend/tests/etl/test_extract.py
git commit -m "feat(etl): extract module + fixture dataset"
```

---

### Task 5: Transform module

**Files:**
- Create: `backend/app/etl/transform.py`
- Test: `backend/tests/etl/test_transform.py`

**Interfaces:**
- Consumes: `RawQuestion` (Task 4), `QuestionType`/`QuestionStatus` (`app.models.enums`).
- Produces: `CleanedQuestion`/`CleanedOption` dataclasses; `validate(raw) -> list[str]`; `transform(raw, language, pending_translation_ids=None) -> CleanedQuestion`.

- [ ] **Step 1: Write the failing test**

`backend/tests/etl/test_transform.py`:
```python
from app.etl.extract import Bilingual, RawOption, RawQuestion, RawSource
from app.etl.transform import transform, validate
from app.models.enums import QuestionType


def _raw(type_: str, correct_keys, prompt_items=None, zh_stem="单选", zh_options=None):
    options = [
        RawOption(key="A", text=Bilingual(en="A", zh=(zh_options or {}).get("A", "甲"))),
        RawOption(key="B", text=Bilingual(en="B", zh=(zh_options or {}).get("B", "乙"))),
    ]
    return RawQuestion(
        id="t1",
        source=RawSource("Book", 1, "review", 1, "Title", 1),
        type=type_,
        stem=Bilingual(en="Stem", zh=zh_stem),
        options=options,
        correct_keys=correct_keys,
        explanation=Bilingual(en="Exp", zh="解析"),
        meta={"choose_all": False, "matching": type_ == "matching", "issues": [], "zh_source": "v9", "zh_issues": []},
        prompt_items=prompt_items,
    )


def test_matching_normalizes_to_single_choice_with_prompt_items():
    raw = _raw("matching", ["B"], prompt_items=[RawPromptItemDummy])
    # prompt_items real test below uses a raw built with prompt_items
    cleaned = transform(raw, "en")
    assert cleaned.question_type is QuestionType.single_choice
    assert cleaned.prompt_items is not None


def test_single_choice_passes_through():
    raw = _raw("single_choice", ["A"])
    cleaned = transform(raw, "en")
    assert cleaned.question_type is QuestionType.single_choice
    assert cleaned.prompt_items is None


def test_multiple_choice_passes_through():
    raw = _raw("multiple_choice", ["A", "B"])
    cleaned = transform(raw, "en")
    assert cleaned.question_type is QuestionType.multiple_choice


def test_bilingual_split_en_vs_zh():
    raw = _raw("single_choice", ["A"], zh_stem="题干")
    en = transform(raw, "en")
    zh = transform(raw, "zh")
    assert en.stem == "Stem"
    assert zh.stem == "题干"
    assert en.options[0].content == "A"
    assert zh.options[0].content == "甲"


def test_missing_zh_marks_needs_revision_and_falls_back():
    raw = _raw("single_choice", ["A"], zh_stem="", zh_options={"A": "", "B": ""})
    zh = transform(raw, "zh")
    assert zh.needs_revision is True
    assert zh.stem == "Stem"  # fell back to en
    assert "missing_zh" in zh.issues


def test_is_correct_from_correct_keys():
    raw = _raw("multiple_choice", ["A", "B"])
    cleaned = transform(raw, "en")
    assert [o.is_correct for o in cleaned.options] == [True, True]
    raw2 = _raw("single_choice", ["B"])
    cleaned2 = transform(raw2, "en")
    assert [o.is_correct for o in cleaned2.options] == [False, True]


def test_default_difficulty_and_chapter():
    raw = _raw("single_choice", ["A"])
    cleaned = transform(raw, "en")
    assert cleaned.difficulty == 3
    assert cleaned.source_chapter == 1
    assert cleaned.source_chapter_title == "Title"


def test_validate_single_choice_requires_exactly_one_correct():
    raw = _raw("single_choice", ["A", "B"])
    issues = validate(raw)
    assert any("exactly 1" in i for i in issues)


def test_validate_multiple_choice_requires_at_least_two():
    raw = _raw("multiple_choice", ["A"])
    issues = validate(raw)
    assert any("at least 2" in i for i in issues)


def test_validate_correct_keys_subset_of_options():
    raw = _raw("single_choice", ["Z"])
    issues = validate(raw)
    assert any("not in options" in i for i in issues)


# dummy used by the matching test above; replaced with real RawPromptItem
from app.etl.extract import RawPromptItem  # noqa: E402
RawPromptItemDummy = RawPromptItem(key="1", text=Bilingual(en="X", zh="X"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/etl/test_transform.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.etl.transform'`

- [ ] **Step 3: Write `backend/app/etl/transform.py`**

```python
"""ETL Transform: pure functions turning RawQuestion -> per-language CleanedQuestion.

No DB, no I/O. Deterministic: same raw in -> same cleaned out.
"""

from dataclasses import dataclass

from app.etl.extract import RawQuestion
from app.models.enums import QuestionType

DIFFICULTY_DEFAULT = 3  # medium


@dataclass
class CleanedOption:
    key: str
    content: str
    is_correct: bool


@dataclass
class CleanedQuestion:
    external_id: str
    language: str
    question_type: QuestionType
    stem: str
    options: list[CleanedOption]
    explanation: str
    prompt_items: list | None
    source_chapter: int
    source_chapter_title: str
    difficulty: int
    issues: list[str]
    needs_revision: bool


def _normalize_type(raw_type: str) -> QuestionType:
    if raw_type == "matching":
        return QuestionType.single_choice
    return QuestionType(raw_type)


def validate(raw: RawQuestion) -> list[str]:
    issues: list[str] = []
    option_keys = {o.key for o in raw.options}
    for k in raw.correct_keys:
        if k not in option_keys:
            issues.append(f"correct_key '{k}' not in options")
    if raw.type == "single_choice" or raw.type == "matching":
        if len(raw.correct_keys) != 1:
            issues.append("single_choice requires exactly 1 correct key")
    elif raw.type == "multiple_choice":
        if len(raw.correct_keys) < 2:
            issues.append("multiple_choice requires at least 2 correct keys")
    return issues


def transform(
    raw: RawQuestion,
    language: str,
    pending_translation_ids: set[str] | None = None,
) -> CleanedQuestion:
    pending_translation_ids = pending_translation_ids or set()
    issues: list[str] = list(raw.meta.get("issues", [])) + list(raw.meta.get("zh_issues", []))
    if raw.id in pending_translation_ids:
        issues.append("translation_pending")

    needs_revision = False

    def pick(en: str, zh: str) -> str:
        nonlocal needs_revision
        if language == "zh":
            if not zh or not zh.strip():
                needs_revision = True
                issues.append("missing_zh")
                return en  # fall back to en so the row is not blank
            return zh
        return en

    stem = pick(raw.stem.en, raw.stem.zh)
    explanation = pick(raw.explanation.en, raw.explanation.zh)

    options = [
        CleanedOption(
            key=o.key,
            content=pick(o.text.en, o.text.zh),
            is_correct=o.key in raw.correct_keys,
        )
        for o in raw.options
    ]

    prompt_items = None
    if raw.type == "matching" and raw.prompt_items:
        prompt_items = [
            {"key": p.key, "text": {"en": p.text.en, "zh": p.text.zh}}
            for p in raw.prompt_items
        ]

    return CleanedQuestion(
        external_id=raw.id,
        language=language,
        question_type=_normalize_type(raw.type),
        stem=stem,
        options=options,
        explanation=explanation,
        prompt_items=prompt_items,
        source_chapter=raw.source.chapter,
        source_chapter_title=raw.source.chapter_title,
        difficulty=DIFFICULTY_DEFAULT,
        issues=issues,
        needs_revision=needs_revision,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/etl/test_transform.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/etl/transform.py backend/tests/etl/test_transform.py
git commit -m "feat(etl): transform module (pure normalization rules)"
```

---

### Task 6: Load module

**Files:**
- Create: `backend/app/etl/load.py`
- Test: `backend/tests/etl/test_load.py`

**Interfaces:**
- Consumes: `CleanedQuestion` (Task 5); models `Question`/`QuestionOption`/`Explanation`/`QuestionMapping`/`QuestionExternalKey`/`ChapterDomainMapping`/`Book`/`Chapter`/`ImportJob`; `snapshot_question()` (`app.services.snapshot`); enums `QuestionStatus`/`LicenseStatus`/`TextFormat`/`QuestionType`.
- Produces: `LoadResult`/`DryRunSummary` dataclasses; `apply_load(session, org_id, dataset_slug, import_job_id, cleaned) -> LoadResult`; `apply_dry_run(session, org_id, dataset_slug, cleaned) -> DryRunSummary`.

- [ ] **Step 1: Write the failing test**

`backend/tests/etl/test_load.py`:
```python
import uuid

from sqlalchemy import select

from app.etl.load import LoadResult, apply_dry_run, apply_load
from app.etl.transform import CleanedOption, CleanedQuestion
from app.models.enums import QuestionType
from app.models.question import (
    Book,
    Chapter,
    Question,
    QuestionExternalKey,
    QuestionOption,
    QuestionRevision,
)
from app.models.etl import ChapterDomainMapping
from app.models.taxonomy import ExamBlueprint, ExamDomain
from datetime import date


def _cleaned(external_id="c1", lang="en", stem="Stem", explanation="Exp"):
    return CleanedQuestion(
        external_id=external_id,
        language=lang,
        question_type=QuestionType.single_choice,
        stem=stem,
        options=[CleanedOption(key="A", content="A", is_correct=True),
                 CleanedOption(key="B", content="B", is_correct=False)],
        explanation=explanation,
        prompt_items=None,
        source_chapter=1,
        source_chapter_title="Chapter One",
        difficulty=3,
        issues=[],
        needs_revision=False,
    )


def _seed_org_and_domain(session):
    from app.models.auth import Organization
    from app.models.enums import OrgKind
    org = Organization(slug="t-org", name="T", kind=OrgKind.personal)
    session.add(org)
    session.flush()
    bp = ExamBlueprint(version_label="t", effective_date=date(2024, 4, 15),
                       min_items=1, max_items=2, duration_minutes=60,
                       passing_score=700, max_score=1000, is_current=True)
    session.add(bp)
    session.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="Dom1", weight_pct=10)
    session.add(dom)
    session.flush()
    cdm = ChapterDomainMapping(dataset_slug="osg10", chapter_number=1,
                               domain_id=dom.id, chapter_title="Chapter One")
    session.add(cdm)
    session.flush()
    return org.id


def test_apply_load_creates_question_and_links(db_session):
    org_id = _seed_org_and_domain(db_session)
    cleaned = [_cleaned()]
    result = apply_load(db_session, org_id, "osg10", None, cleaned)
    assert result.created == 1
    assert result.updated == 0
    assert result.unchanged == 0
    q = db_session.execute(select(Question)).scalar_one()
    assert q.stem == "Stem"
    assert q.organization_id == org_id
    # external key
    key = db_session.execute(select(QuestionExternalKey)).scalar_one()
    assert key.external_id == "c1"
    assert key.language == "en"
    assert key.question_id == q.id
    # options
    opts = db_session.execute(select(QuestionOption)).scalars().all()
    assert len(opts) == 2
    # mapping has domain_id
    from app.models.question import QuestionMapping
    mapping = db_session.execute(select(QuestionMapping)).scalar_one()
    assert mapping.domain_id is not None


def test_apply_load_update_writes_revision_and_bumps_version(db_session):
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned(stem="Old")])
    # second run with changed stem
    result = apply_load(db_session, org_id, "osg10", None, [_cleaned(stem="New")])
    assert result.updated == 1
    q = db_session.execute(select(Question)).scalar_one()
    assert q.stem == "New"
    assert q.version == 2
    rev = db_session.execute(select(QuestionRevision)).scalar_one()
    assert rev.snapshot["stem"] == "Old"


def test_apply_load_unchanged_skips_revision(db_session):
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned()])
    result = apply_load(db_session, org_id, "osg10", None, [_cleaned()])
    assert result.unchanged == 1
    assert result.updated == 0
    assert db_session.execute(select(QuestionRevision)).scalars().all() == []


def test_apply_load_error_isolation(db_session):
    org_id = _seed_org_and_domain(db_session)
    # a cleaned record with zero options would violate NOT NULL? Instead force
    # an error by reusing an external_id but a different language that collides:
    # we make a malformed cleaned whose question_type is fine but stem is set so
    # that the second record has a duplicate (external_id, language) -> handled
    # by update path, not error. Use a record whose options list causes a DB
    # error: empty options is allowed at model level, so inject a None stem.
    bad = CleanedQuestion(
        external_id="bad", language="en", question_type=QuestionType.single_choice,
        stem=None,  # type: ignore  -- will violate NOT NULL on insert
        options=[], explanation="e", prompt_items=None, source_chapter=1,
        source_chapter_title="C", difficulty=3, issues=[], needs_revision=False,
    )
    good = _cleaned()
    result = apply_load(db_session, org_id, "osg10", None, [good, bad])
    assert result.created == 1  # good one survived
    assert len(result.errors) == 1
    assert result.errors[0]["external_id"] == "bad"


def test_apply_dry_run_classifies_without_writing(db_session):
    org_id = _seed_org_and_domain(db_session)
    summary = apply_dry_run(db_session, org_id, "osg10", [_cleaned()])
    assert summary.would_create == 1
    assert summary.would_update == 0
    assert summary.unchanged == 0
    assert db_session.execute(select(Question)).scalars().all() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/etl/test_load.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.etl.load'`

- [ ] **Step 3: Write `backend/app/etl/load.py`**

```python
"""ETL Load: apply CleanedQuestion create-or-update within one transaction.

Owns all DB access and dedup by (dataset_slug, external_id, language).
Savepoint-per-record for error isolation. Caller controls commit.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import LicenseStatus, QuestionStatus, TextFormat
from app.models.etl import ChapterDomainMapping, QuestionExternalKey
from app.models.question import (
    Book,
    Chapter,
    Explanation,
    Question,
    QuestionMapping,
    QuestionOption,
    QuestionRevision,
)
from app.services.snapshot import snapshot_question


@dataclass
class LoadResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    errors: list[dict] = field(default_factory=list)


@dataclass
class DryRunSummary:
    would_create: int = 0
    would_update: int = 0
    unchanged: int = 0
    errors: list[dict] = field(default_factory=list)
    by_type: dict = field(default_factory=dict)
    by_language: dict = field(default_factory=dict)


class _Resolvers:
    """Caches Book/Chapter/Domain lookups for a batch."""

    def __init__(self, session: Session, org_id: uuid.UUID, dataset_slug: str):
        self.session = session
        self.org_id = org_id
        self.dataset_slug = dataset_slug
        self._books: dict[tuple[str, str], Book] = {}
        self._chapters: dict[tuple[uuid.UUID, int], Chapter] = {}
        self._domains: dict[int, uuid.UUID | None] = {}

    def book(self, cleaned) -> Book:
        key = ("CISSP OSG", "10")
        if key not in self._books:
            book = self.session.execute(
                select(Book).filter_by(title="CISSP OSG", edition="10", organization_id=self.org_id)
            ).scalar_one_or_none()
            if book is None:
                book = Book(title="CISSP OSG", edition="10", organization_id=self.org_id)
                self.session.add(book)
                self.session.flush()
            self._books[key] = book
        return self._books[key]

    def chapter(self, cleaned) -> Chapter:
        book = self.book(cleaned)
        key = (book.id, cleaned.source_chapter)
        if key not in self._chapters:
            ch = self.session.execute(
                select(Chapter).filter_by(book_id=book.id, order_index=cleaned.source_chapter)
            ).scalar_one_or_none()
            if ch is None:
                ch = Chapter(
                    book_id=book.id,
                    order_index=cleaned.source_chapter,
                    title=cleaned.source_chapter_title,
                    organization_id=self.org_id,
                )
                self.session.add(ch)
                self.session.flush()
            self._chapters[key] = ch
        return self._chapters[key]

    def domain_id(self, cleaned) -> uuid.UUID | None:
        if cleaned.source_chapter not in self._domains:
            cdm = self.session.execute(
                select(ChapterDomainMapping).filter_by(
                    dataset_slug=self.dataset_slug, chapter_number=cleaned.source_chapter
                )
            ).scalar_one_or_none()
            self._domains[cleaned.source_chapter] = cdm.domain_id if cdm else None
        return self._domains[cleaned.source_chapter]


def _existing_key(session, dataset_slug, external_id, language) -> QuestionExternalKey | None:
    return session.execute(
        select(QuestionExternalKey).filter_by(
            dataset_slug=dataset_slug, external_id=external_id, language=language
        )
    ).scalar_one_or_none()


def _current_options(session, question_id) -> list[QuestionOption]:
    return list(
        session.execute(
            select(QuestionOption).filter_by(question_id=question_id).order_by(QuestionOption.order_index)
        ).scalars()
    )


def _differs(q: Question, options: list[QuestionOption], cleaned) -> bool:
    if q.stem != cleaned.stem:
        return True
    if q.question_type != cleaned.question_type:
        return True
    if [o.content for o in options] != [o.content for o in cleaned.options]:
        return True
    if [o.is_correct for o in options] != [o.is_correct for o in cleaned.options]:
        return True
    return False


def _apply_one(session, resolvers, dataset_slug, import_job_id, cleaned) -> str:
    """Apply one cleaned record. Returns 'created'|'updated'|'unchanged'."""
    existing = _existing_key(session, dataset_slug, cleaned.external_id, cleaned.language)
    status = QuestionStatus.needs_revision if cleaned.needs_revision else QuestionStatus.draft

    if existing is None:
        q = Question(
            organization_id=resolvers.org_id,
            question_type=cleaned.question_type,
            stem=cleaned.stem,
            stem_format=TextFormat.markdown,
            difficulty=cleaned.difficulty,
            language=cleaned.language,
            status=status,
            source=cleaned.external_id,
            license_status=LicenseStatus.unconfirmed,
            import_job_id=import_job_id,
            prompt_items=cleaned.prompt_items,
        )
        session.add(q)
        session.flush()
        for i, opt in enumerate(cleaned.options):
            session.add(QuestionOption(
                question_id=q.id, order_index=i, content=opt.content,
                content_format=TextFormat.markdown, is_correct=opt.is_correct,
            ))
        session.add(Explanation(
            question_id=q.id, correct_answer_rationale=cleaned.explanation,
        ))
        session.add(QuestionExternalKey(
            dataset_slug=dataset_slug, external_id=cleaned.external_id,
            language=cleaned.language, question_id=q.id,
        ))
        ch = resolvers.chapter(cleaned)
        session.add(QuestionMapping(
            question_id=q.id, chapter_id=ch.id, domain_id=resolvers.domain_id(cleaned),
        ))
        return "created"

    q = session.get(Question, existing.question_id)
    options = _current_options(session, q.id)
    if not _differs(q, options, cleaned):
        return "unchanged"

    # historical integrity: snapshot BEFORE update
    old_snap = snapshot_question(q, options)
    session.add(QuestionRevision(
        question_id=q.id, revision_number=q.version, snapshot=old_snap,
        change_summary="etl update",
    ))
    q.stem = cleaned.stem
    q.question_type = cleaned.question_type
    q.difficulty = cleaned.difficulty
    q.status = status
    q.prompt_items = cleaned.prompt_items
    q.version = (q.version or 1) + 1
    # replace options
    for o in options:
        session.delete(o)
    session.flush()
    for i, opt in enumerate(cleaned.options):
        session.add(QuestionOption(
            question_id=q.id, order_index=i, content=opt.content,
            content_format=TextFormat.markdown, is_correct=opt.is_correct,
        ))
    # update explanation
    expl = session.execute(select(Explanation).filter_by(question_id=q.id)).scalar_one_or_none()
    if expl is None:
        session.add(Explanation(question_id=q.id, correct_answer_rationale=cleaned.explanation))
    else:
        expl.correct_answer_rationale = cleaned.explanation
    return "updated"


def apply_load(session, org_id, dataset_slug, import_job_id, cleaned_list) -> LoadResult:
    resolvers = _Resolvers(session, org_id, dataset_slug)
    result = LoadResult()
    for cleaned in cleaned_list:
        try:
            sp = session.begin_nested()
            outcome = _apply_one(session, resolvers, dataset_slug, import_job_id, cleaned)
            sp.commit()
            if outcome == "created":
                result.created += 1
            elif outcome == "updated":
                result.updated += 1
            else:
                result.unchanged += 1
        except Exception as exc:
            # Roll back ONLY this record's savepoint — a bare session.rollback()
            # would undo the outer transaction and lose prior records' commits.
            try:
                sp.rollback()
            except Exception:
                pass
            result.errors.append({
                "external_id": cleaned.external_id,
                "language": cleaned.language,
                "reason": f"{type(exc).__name__}: {exc}",
            })
    return result


def apply_dry_run(session, org_id, dataset_slug, cleaned_list) -> DryRunSummary:
    summary = DryRunSummary()
    for cleaned in cleaned_list:
        summary.by_type[cleaned.question_type.value] = summary.by_type.get(cleaned.question_type.value, 0) + 1
        summary.by_language[cleaned.language] = summary.by_language.get(cleaned.language, 0) + 1
        existing = _existing_key(session, dataset_slug, cleaned.external_id, cleaned.language)
        if existing is None:
            summary.would_create += 1
            continue
        q = session.get(Question, existing.question_id)
        options = _current_options(session, q.id)
        summary.would_update += 1 if _differs(q, options, cleaned) else 0
        summary.unchanged += 0 if _differs(q, options, cleaned) else 1
    return summary
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/etl/test_load.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/etl/load.py backend/tests/etl/test_load.py
git commit -m "feat(etl): load module (create/update/dedup/savepoint isolation)"
```

---

### Task 7: Runner module

**Files:**
- Create: `backend/app/etl/runner.py`
- Test: `backend/tests/etl/test_runner.py`

**Interfaces:**
- Consumes: `DatasetReader` (Task 4), `transform`/`validate` (Task 5), `apply_load`/`apply_dry_run` (Task 6); models `EtlDataset`/`EtlRun`/`ImportJob`; `log_audit()` (`app.services.audit`); `AuditAction.import_action`.
- Produces: `EtlDriftError`; `run_preview(session, org_id, dataset, initiated_by_id=None) -> EtlRun`; `run_commit(session, org_id, run_id) -> EtlRun`; `run_rollback(session, run_id) -> EtlRun`.

- [ ] **Step 1: Write the failing test**

`backend/tests/etl/test_runner.py`:
```python
from datetime import date

import pytest
from sqlalchemy import select

from app.etl.runner import EtlDriftError, run_commit, run_preview, run_rollback
from app.models.auth import Organization
from app.models.enums import ImportFormat, ImportStatus, OrgKind
from app.models.etl import EtlDataset, EtlRun, QuestionExternalKey
from app.models.question import ImportJob, Question
from app.models.taxonomy import ExamBlueprint, ExamDomain
from app.models.etl import ChapterDomainMapping
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "mini"


def _seed(session):
    org = Organization(slug="r-org", name="R", kind=OrgKind.personal)
    session.add(org)
    session.flush()
    bp = ExamBlueprint(version_label="r", effective_date=date(2024, 4, 15),
                       min_items=1, max_items=2, duration_minutes=60,
                       passing_score=700, max_score=1000, is_current=True)
    session.add(bp)
    session.flush()
    for n in (1, 2):
        session.add(ExamDomain(blueprint_id=bp.id, number=n, name=f"D{n}", weight_pct=10))
    session.flush()
    d1 = session.execute(select(ExamDomain).filter_by(number=1)).scalar_one()
    d2 = session.execute(select(ExamDomain).filter_by(number=2)).scalar_one()
    session.add(ChapterDomainMapping(dataset_slug="mini", chapter_number=1, domain_id=d1.id, chapter_title="Chapter One"))
    session.add(ChapterDomainMapping(dataset_slug="mini", chapter_number=2, domain_id=d2.id, chapter_title="Chapter Two"))
    session.flush()
    ds = EtlDataset(
        organization_id=org.id, slug="mini", name="Mini", source_path=str(FIXTURE),
        format=ImportFormat.json, total_questions=3, languages=["en", "zh"],
    )
    session.add(ds)
    session.flush()
    return org.id, ds


def test_preview_writes_no_questions(db_session):
    org_id, ds = _seed(db_session)
    run = run_preview(db_session, org_id, ds)
    assert run.phase.value == "preview"
    assert db_session.execute(select(Question)).scalars().all() == []
    summary = run.preview_summary
    # 3 raws x 2 langs = 6 would-create (no existing)
    assert summary["would_create"] == 6
    job = db_session.get(ImportJob, run.import_job_id)
    assert job.status == ImportStatus.previewing


def test_commit_writes_rows(db_session):
    org_id, ds = _seed(db_session)
    run = run_preview(db_session, org_id, ds)
    committed = run_commit(db_session, org_id, run.id)
    assert committed.phase.value == "committed"
    # 3 questions x 2 langs
    assert db_session.execute(select(Question)).scalars().all().__len__() == 6
    keys = db_session.execute(select(QuestionExternalKey)).scalars().all()
    assert len(keys) == 6
    job = db_session.get(ImportJob, committed.import_job_id)
    assert job.status == ImportStatus.completed


def test_commit_is_idempotent(db_session):
    org_id, ds = _seed(db_session)
    run = run_preview(db_session, org_id, ds)
    run_commit(db_session, org_id, run.id)
    run2 = run_preview(db_session, org_id, ds)
    committed = run_commit(db_session, org_id, run2.id)
    # still only 6 questions
    assert db_session.execute(select(Question)).scalars().all().__len__() == 6
    # second commit's import job reflects all-unchanged
    job = db_session.get(ImportJob, committed.import_job_id)
    assert job.success_count == 0  # nothing newly created
    assert job.status == ImportStatus.completed


def test_rollback_flips_status_and_writes_nothing(db_session):
    org_id, ds = _seed(db_session)
    run = run_preview(db_session, org_id, ds)
    rolled = run_rollback(db_session, run.id)
    assert rolled.phase.value == "rolled_back"
    assert db_session.execute(select(Question)).scalars().all() == []
    job = db_session.get(ImportJob, rolled.import_job_id)
    assert job.status == ImportStatus.failed


def test_drift_check_raises(db_session, monkeypatch):
    org_id, ds = _seed(db_session)
    run = run_preview(db_session, org_id, ds)
    # tamper: change stored hash so re-read hash differs
    run.preview_summary = {**run.preview_summary, "content_hash": "0" * 64}
    db_session.flush()
    with pytest.raises(EtlDriftError):
        run_commit(db_session, org_id, run.id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/etl/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.etl.runner'`

- [ ] **Step 3: Write `backend/app/etl/runner.py`**

```python
"""ETL Runner: orchestrate extract -> transform -> load across preview/commit.

Owns the session lifecycle and writes EtlRun/ImportJob.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.etl.extract import DatasetReader
from app.etl.load import apply_dry_run, apply_load
from app.etl.transform import transform, validate
from app.models.enums import AuditAction, ImportFormat, ImportStatus, LicenseStatus
from app.models.etl import EtlDataset, EtlRun
from app.models.question import ImportJob
from app.services.audit import log_audit


class EtlDriftError(Exception):
    """Dataset files changed between preview and commit."""


def _build_cleaned(raws, languages, pending_ids):
    cleaned = []
    errors = []
    for raw in raws:
        issues = validate(raw)
        if issues:
            errors.append({
                "external_id": raw.id,
                "language": None,
                "reason": "validation: " + "; ".join(issues),
            })
            continue
        for lang in languages:
            cleaned.append(transform(raw, lang, pending_ids))
    return cleaned, errors


def run_preview(session: Session, org_id: uuid.UUID, dataset: EtlDataset, initiated_by_id=None) -> EtlRun:
    job = ImportJob(
        organization_id=org_id,
        format=dataset.format,
        source=dataset.source_path,
        license_status=LicenseStatus.unconfirmed,
        status=ImportStatus.previewing,
        initiated_by_id=initiated_by_id,
    )
    session.add(job)
    session.flush()

    run = EtlRun(
        organization_id=org_id,
        dataset_id=dataset.id,
        import_job_id=job.id,
        phase="preview",  # type: ignore[arg-type]
    )
    session.add(run)
    session.flush()

    raws, extract_errors, content_hash = DatasetReader(dataset.source_path).read()
    pending_ids = set()  # translate_queue.json empty for osg10; read from manifest if present
    cleaned, transform_errors = _build_cleaned(raws, dataset.languages, pending_ids)

    summary = apply_dry_run(session, org_id, dataset.slug, cleaned)
    all_errors = (
        [{"external_id": e.external_id, "language": None, "reason": e.reason} for e in extract_errors]
        + transform_errors
        + summary.errors
    )

    preview_summary = {
        "would_create": summary.would_create,
        "would_update": summary.would_update,
        "unchanged": summary.unchanged,
        "by_type": summary.by_type,
        "by_language": summary.by_language,
        "errors": all_errors,
        "content_hash": content_hash,
    }
    run.preview_summary = preview_summary
    job.total_rows = len(cleaned)
    job.error_count = len(all_errors)
    session.flush()
    return run


def run_commit(session: Session, org_id: uuid.UUID, run_id: uuid.UUID) -> EtlRun:
    run = session.get(EtlRun, run_id)
    if run is None or run.phase.value != "preview":
        raise ValueError(f"run {run_id} not in preview phase")
    dataset = session.get(EtlDataset, run.dataset_id)

    raws, extract_errors, content_hash = DatasetReader(dataset.source_path).read()
    if content_hash != run.preview_summary.get("content_hash"):
        raise EtlDriftError("dataset changed since preview; re-preview required")

    pending_ids = set()
    cleaned, transform_errors = _build_cleaned(raws, dataset.languages, pending_ids)
    load_result = apply_load(session, org_id, dataset.slug, run.import_job_id, cleaned)

    run.phase = "committed"  # type: ignore[assignment]
    run.committed_at = datetime.now(timezone.utc)

    job = session.get(ImportJob, run.import_job_id)
    job.status = ImportStatus.completed if not load_result.errors else ImportStatus.partial
    job.total_rows = len(cleaned)
    job.success_count = load_result.created + load_result.updated + load_result.unchanged
    job.error_count = len(load_result.errors) + len(transform_errors)
    job.error_report = {"errors": load_result.errors + transform_errors}

    log_audit(
        session,
        action=AuditAction.import_action,
        actor_id=None,
        organization_id=org_id,
        entity_type="etl_run",
        entity_id=str(run.id),
        details={"dataset": dataset.slug, "created": load_result.created,
                 "updated": load_result.updated, "unchanged": load_result.unchanged},
    )
    session.flush()
    return run


def run_rollback(session: Session, run_id: uuid.UUID) -> EtlRun:
    run = session.get(EtlRun, run_id)
    if run is None or run.phase.value != "preview":
        raise ValueError(f"run {run_id} not in preview phase")
    run.phase = "rolled_back"  # type: ignore[assignment]
    job = session.get(ImportJob, run.import_job_id)
    job.status = ImportStatus.failed
    session.flush()
    return run
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/etl/test_runner.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/etl/runner.py backend/tests/etl/test_runner.py
git commit -m "feat(etl): runner (preview/commit/rollback two-phase lifecycle)"
```

---

### Task 8: Seed osg10 dataset + chapter→domain mappings

**Files:**
- Modify: `backend/app/db/seed.py`
- Modify: `backend/tests/test_seed.py`
- Test: existing `backend/tests/test_seed.py`

**Interfaces:**
- Consumes: `EtlDataset`, `ChapterDomainMapping`, `ExamDomain` (already seeded), `ImportFormat`.
- Produces: seeded `osg10` dataset + 21 `ChapterDomainMapping` rows; `SEED_VERSION` bumped to `"2"`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_seed.py` (create if it does not exist):
```python
from sqlalchemy import select

from app.db.seed import run_seed
from app.models.etl import ChapterDomainMapping, EtlDataset


def test_seed_creates_osg10_dataset_and_mappings(db_session):
    run_seed(db_session)
    ds = db_session.execute(select(EtlDataset).filter_by(slug="osg10")).scalar_one()
    assert ds.total_questions == 420
    assert ds.languages == ["en", "zh"]
    mappings = db_session.execute(
        select(ChapterDomainMapping).filter_by(dataset_slug="osg10")
    ).scalars().all()
    assert len(mappings) == 21


def test_seed_is_idempotent(db_session):
    run_seed(db_session)
    run_seed(db_session)
    count = len(
        db_session.execute(
            select(ChapterDomainMapping).filter_by(dataset_slug="osg10")
        ).scalars().all()
    )
    assert count == 21
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_seed.py -v`
Expected: FAIL (`EtlDataset osg10` not found / 0 mappings)

- [ ] **Step 3: Modify `backend/app/db/seed.py`**

Change `SEED_VERSION = "1"` to `SEED_VERSION = "2"`.

Add imports at top:
```python
from app.models.etl import ChapterDomainMapping, EtlDataset
from app.models.enums import ImportFormat
```

Add this block at the end of `run_seed`, before the `# Seed version marker.` comment. Map chapter→domain `number` (NOT name — the seed uses `"Identity and Access Management (IAM)"` for domain 5, so name-matching would fail):

```python
    # OSG v10 dataset + chapter->domain mapping (PRD §9.4, spec §9).
    osg10_path = "docs/questions/osg10"
    _get_or_create(
        session,
        EtlDataset,
        slug="osg10",
        defaults={
            "organization_id": personal_org.id,
            "name": "CISSP OSG v10",
            "source_path": osg10_path,
            "format": ImportFormat.json,
            "total_questions": 420,
            "languages": ["en", "zh"],
            "notes": "OSG 10th edition review questions, bilingual en/zh",
        },
    )
    domain_by_number = {
        d.number: d
        for d in session.execute(select(ExamDomain).filter_by(blueprint_id=bp.id)).scalars()
    }
    # (chapter_number, chapter_title) -> domain number
    osg10_chapters = [
        (1, "Security Governance Through Principles and Policies", 1),
        (2, "Personnel Security and Risk Management Concepts", 1),
        (3, "Business Continuity Planning", 1),
        (4, "Laws, Regulations, and Compliance", 1),
        (5, "Protecting Security of Assets", 2),
        (6, "Cryptography and Symmetric Key Algorithms", 3),
        (7, "PKI and Cryptographic Applications", 3),
        (8, "Principles of Security Models, Design, and Capabilities", 3),
        (9, "Security Vulnerabilities, Threats, and Countermeasures", 3),
        (10, "Physical Security Requirements", 3),
        (11, "Secure Network Architecture and Components", 4),
        (12, "Secure Communications and Network Attacks", 4),
        (13, "Managing Identity and Authentication", 5),
        (14, "Controlling and Monitoring Access", 5),
        (15, "Security Assessment and Testing", 6),
        (16, "Managing Security Operations", 7),
        (17, "Preventing and Responding to Incidents", 7),
        (18, "Disaster Recovery Planning", 7),
        (19, "Investigations and Ethics", 7),
        (20, "Software Development Security", 8),
        (21, "Malicious Code and Application Attacks", 8),
    ]
    for chapter_number, chapter_title, domain_number in osg10_chapters:
        _get_or_create(
            session,
            ChapterDomainMapping,
            dataset_slug="osg10",
            chapter_number=chapter_number,
            defaults={
                "domain_id": domain_by_number[domain_number].id,
                "chapter_title": chapter_title,
            },
        )
    session.flush()
```

Also capture the personal org id: change the existing org `_get_or_create` call to assign to `personal_org`:
```python
    personal_org = _get_or_create(
        session,
        Organization,
        slug="personal",
        defaults={"name": "Personal", "kind": OrgKind.personal},
    )
```

Add `"datasets"` and `"chapter_mappings"` to the `counts` dict and set `counts["datasets"] = 1`, `counts["chapter_mappings"] = len(osg10_chapters)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_seed.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/seed.py backend/tests/test_seed.py
git commit -m "feat(etl): seed osg10 dataset + 21 chapter->domain mappings"
```

---

### Task 9: HTTP API router

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/etl.py`
- Modify: `backend/app/main.py` (mount router)
- Test: `backend/tests/etl/test_api_etl.py`

**Interfaces:**
- Consumes: `run_preview`/`run_commit`/`run_rollback` (Task 7), `EtlDataset`/`EtlRun`/`ChapterDomainMapping` models, `app.db.session.get_session`.
- Produces: FastAPI router at `/api/etl` with endpoints listed in spec §8.

- [ ] **Step 1: Write the failing test**

`backend/tests/etl/test_api_etl.py`:
```python
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.etl import router as etl_router
from app.db.session import get_session
from app.main import create_app
from app.models.auth import Organization
from app.models.enums import ImportFormat, OrgKind
from app.models.etl import ChapterDomainMapping, EtlDataset
from app.models.taxonomy import ExamBlueprint, ExamDomain

FIXTURE = Path(__file__).parent / "fixtures" / "mini"


@pytest.fixture
def client(db_session):
    """A TestClient whose /api/etl routes share the test's own session/connection.

    The db_session fixture holds an uncommitted savepoint on its connection; if
    the app opened its own session it would not see that data. Overriding
    get_session to return db_session makes the app read/write through the same
    connection the test seeds.
    """
    app = create_app()

    def _override_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    return TestClient(app)


def _seed(session):
    org = Organization(slug="api-org", name="API", kind=OrgKind.personal)
    session.add(org); session.flush()
    bp = ExamBlueprint(version_label="api", effective_date=date(2024, 4, 15),
                       min_items=1, max_items=2, duration_minutes=60,
                       passing_score=700, max_score=1000, is_current=True)
    session.add(bp); session.flush()
    for n in (1, 2):
        session.add(ExamDomain(blueprint_id=bp.id, number=n, name=f"D{n}", weight_pct=10))
    session.flush()
    d1 = session.execute(select(ExamDomain).filter_by(number=1)).scalar_one()
    d2 = session.execute(select(ExamDomain).filter_by(number=2)).scalar_one()
    session.add(ChapterDomainMapping(dataset_slug="mini", chapter_number=1, domain_id=d1.id, chapter_title="Chapter One"))
    session.add(ChapterDomainMapping(dataset_slug="mini", chapter_number=2, domain_id=d2.id, chapter_title="Chapter Two"))
    session.add(EtlDataset(organization_id=org.id, slug="mini", name="Mini", source_path=str(FIXTURE),
                           format=ImportFormat.json, total_questions=3, languages=["en", "zh"]))
    session.flush()
    return org.id


def test_list_datasets(client, db_session):
    _seed(db_session)
    resp = client.get("/api/etl/datasets")
    assert resp.status_code == 200
    slugs = [d["slug"] for d in resp.json()]
    assert "mini" in slugs


def test_get_dataset_404(client, db_session):
    _seed(db_session)
    resp = client.get("/api/etl/datasets/does-not-exist")
    assert resp.status_code == 404


def test_list_mappings(client, db_session):
    _seed(db_session)
    resp = client.get("/api/etl/mappings?dataset_slug=mini")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_create_and_rollback_run(client, db_session):
    org_id = _seed(db_session)
    # preview
    resp = client.post("/api/etl/runs", json={"dataset_slug": "mini"})
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["run_id"]
    assert resp.json()["phase"] == "preview"
    assert resp.json()["preview_summary"]["would_create"] == 6
    # rollback (writes nothing)
    rb = client.post(f"/api/etl/runs/{run_id}/rollback")
    assert rb.status_code == 200
    assert rb.json()["phase"] == "rolled_back"
    from app.models.question import Question
    assert db_session.execute(select(Question)).scalars().all() == []


def test_commit_run_writes_rows(client, db_session):
    _seed(db_session)
    resp = client.post("/api/etl/runs", json={"dataset_slug": "mini"})
    run_id = resp.json()["run_id"]
    commit = client.post(f"/api/etl/runs/{run_id}/commit")
    assert commit.status_code == 200, commit.text
    assert commit.json()["phase"] == "committed"
    from app.models.question import Question
    from sqlalchemy import func
    assert db_session.execute(select(func.count(Question.id))).scalar() == 6
```

Note: the `client` fixture overrides the `get_session` dependency so the FastAPI app shares the test's own `db_session` connection — otherwise the app's separate session could not see the uncommitted savepoint data the test seeds, and `GET /datasets` would return empty. The router still opens its session via the `get_session` dependency in production; the override only swaps which session object is yielded during tests.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/etl/test_api_etl.py -v`
Expected: FAIL (404 / no router)

- [ ] **Step 3: Write `backend/app/api/__init__.py`** (empty)

- [ ] **Step 4: Write `backend/app/api/etl.py`**

```python
"""ETL HTTP API. Unauthenticated stubs until auth/JWT sub-project lands.
Each handler carries # TODO(auth): replace with real org/user from JWT.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.etl.runner import run_commit, run_preview, run_rollback
from app.models.auth import Organization
from app.models.etl import ChapterDomainMapping, EtlDataset, EtlRun

router = APIRouter(prefix="/api/etl", tags=["etl"])


def _org_id(session: Session) -> uuid.UUID:
    # TODO(auth): replace with real org from JWT.
    org = session.execute(select(Organization).limit(1)).scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=500, detail="no organization seeded")
    return org.id


class CreateRunIn(BaseModel):
    dataset_slug: str


class MappingIn(BaseModel):
    dataset_slug: str
    chapter_number: int
    chapter_title: str
    domain_id: uuid.UUID | None = None


@router.get("/datasets")
def list_datasets(session: Session = Depends(get_session)):
    rows = session.execute(select(EtlDataset)).scalars().all()
    return [
        {
            "id": str(d.id), "slug": d.slug, "name": d.name,
            "source_path": d.source_path, "total_questions": d.total_questions,
            "languages": d.languages,
        }
        for d in rows
    ]


@router.get("/datasets/{slug}")
def get_dataset(slug: str, session: Session = Depends(get_session)):
    d = session.execute(select(EtlDataset).filter_by(slug=slug)).scalar_one_or_none()
    if d is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return {"id": str(d.id), "slug": d.slug, "name": d.name,
            "source_path": d.source_path, "total_questions": d.total_questions,
            "languages": d.languages}


@router.post("/runs")
def create_run(body: CreateRunIn, session: Session = Depends(get_session)):
    # TODO(auth): initiated_by_id from JWT.
    org_id = _org_id(session)
    ds = session.execute(select(EtlDataset).filter_by(slug=body.dataset_slug)).scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    run = run_preview(session, org_id, ds)
    session.commit()
    return {"run_id": str(run.id), "phase": run.phase.value, "preview_summary": run.preview_summary}


@router.get("/runs/{run_id}")
def get_run(run_id: uuid.UUID, session: Session = Depends(get_session)):
    run = session.get(EtlRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": str(run.id), "phase": run.phase.value,
            "preview_summary": run.preview_summary, "committed_at": run.committed_at}


@router.post("/runs/{run_id}/commit")
def commit_run(run_id: uuid.UUID, session: Session = Depends(get_session)):
    # TODO(auth): org_id from JWT.
    org_id = _org_id(session)
    try:
        run = run_commit(session, org_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    session.commit()
    return {"run_id": str(run.id), "phase": run.phase.value}


@router.post("/runs/{run_id}/rollback")
def rollback_run(run_id: uuid.UUID, session: Session = Depends(get_session)):
    try:
        run = run_rollback(session, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    session.commit()
    return {"run_id": str(run.id), "phase": run.phase.value}


@router.get("/mappings")
def list_mappings(dataset_slug: str | None = None, session: Session = Depends(get_session)):
    stmt = select(ChapterDomainMapping)
    if dataset_slug:
        stmt = stmt.filter_by(dataset_slug=dataset_slug)
    rows = session.execute(stmt).scalars().all()
    return [
        {"id": str(m.id), "dataset_slug": m.dataset_slug,
         "chapter_number": m.chapter_number, "chapter_title": m.chapter_title,
         "domain_id": str(m.domain_id) if m.domain_id else None}
        for m in rows
    ]


@router.post("/mappings")
def create_mapping(body: MappingIn, session: Session = Depends(get_session)):
    m = ChapterDomainMapping(
        dataset_slug=body.dataset_slug, chapter_number=body.chapter_number,
        chapter_title=body.chapter_title, domain_id=body.domain_id,
    )
    session.add(m)
    session.commit()
    return {"id": str(m.id), "dataset_slug": m.dataset_slug,
            "chapter_number": m.chapter_number}


@router.put("/mappings/{mapping_id}")
def update_mapping(mapping_id: uuid.UUID, body: MappingIn, session: Session = Depends(get_session)):
    m = session.get(ChapterDomainMapping, mapping_id)
    if m is None:
        raise HTTPException(status_code=404, detail="mapping not found")
    m.chapter_title = body.chapter_title
    m.domain_id = body.domain_id
    session.commit()
    return {"id": str(m.id)}


@router.delete("/mappings/{mapping_id}")
def delete_mapping(mapping_id: uuid.UUID, session: Session = Depends(get_session)):
    m = session.get(ChapterDomainMapping, mapping_id)
    if m is None:
        raise HTTPException(status_code=404, detail="mapping not found")
    session.delete(m)
    session.commit()
    return {"deleted": str(mapping_id)}
```

- [ ] **Step 5: Mount the router in `backend/app/main.py`**

Add import and registration inside `create_app()`, after the `/health` route:
```python
from app.api.etl import router as etl_router
```
and inside `create_app()`, before `return app`:
```python
    app.include_router(etl_router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/etl/test_api_etl.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/ backend/app/main.py backend/tests/etl/test_api_etl.py
git commit -m "feat(etl): HTTP API router (unauthenticated stubs)"
```

---

### Task 10: CLI

**Files:**
- Create: `backend/app/etl/cli.py`
- Test: `backend/tests/etl/test_cli.py`

**Interfaces:**
- Consumes: `run_preview`/`run_commit`/`run_rollback` (Task 7), `get_sessionmaker` (`app.db.session`), `EtlDataset`.
- Produces: `python -m app.etl.cli` with `preview`/`commit`/`rollback`/`run` subcommands.

- [ ] **Step 1: Write the failing test**

`backend/tests/etl/test_cli.py`:
```python
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select

from app.db.seed import run_seed
from app.models.etl import EtlDataset


def test_cli_help_runs():
    result = subprocess.run(
        [sys.executable, "-m", "app.etl.cli", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "preview" in result.stdout
    assert "commit" in result.stdout
    assert "run" in result.stdout


def test_cli_preview_osg10_against_real_dataset(db_session, monkeypatch):
    # This is an integration test against the real docs/questions/osg10 dataset.
    # It seeds the osg10 dataset row then invokes run_preview directly, asserting
    # 840 would-create (420 questions x 2 languages).
    run_seed(db_session)
    # Point the dataset source_path at the real repo dataset.
    repo_root = Path(__file__).resolve().parents[3]
    ds = db_session.execute(select(EtlDataset).filter_by(slug="osg10")).scalar_one()
    ds.source_path = str(repo_root / "docs" / "questions" / "osg10")
    db_session.flush()

    from app.etl.runner import run_preview
    from app.models.auth import Organization
    org_id = db_session.execute(select(Organization)).scalar_one().id
    run = run_preview(db_session, org_id, ds)
    assert run.preview_summary["would_create"] == 840
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/etl/test_cli.py -v`
Expected: FAIL (no `app.etl.cli`)

- [ ] **Step 3: Write `backend/app/etl/cli.py`**

```python
"""ETL CLI. Run as `python -m app.etl.cli <command>`.

Commands:
  preview <slug>        dry-run a dataset, print summary
  commit <run_id>       commit a previewed run
  rollback <run_id>     discard a previewed run
  run <slug>            preview + commit in one step
"""

import argparse
import sys
import uuid

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.etl.runner import run_commit, run_preview, run_rollback
from app.models.auth import Organization
from app.models.etl import EtlDataset


def _session():
    return get_sessionmaker()()


def _org_id(session):
    org = session.execute(select(Organization).filter_by(slug="personal")).scalar_one_or_none()
    if org is None:
        org = session.execute(select(Organization).limit(1)).scalar_one()
    return org.id


def _dataset(session, slug):
    ds = session.execute(select(EtlDataset).filter_by(slug=slug)).scalar_one_or_none()
    if ds is None:
        print(f"dataset '{slug}' not found", file=sys.stderr)
        sys.exit(1)
    return ds


def _print_summary(run):
    s = run.preview_summary or {}
    print(f"run_id: {run.id}")
    print(f"phase:  {run.phase.value}")
    print(f"would_create: {s.get('would_create')}")
    print(f"would_update: {s.get('would_update')}")
    print(f"unchanged:    {s.get('unchanged')}")
    print(f"by_type:      {s.get('by_type')}")
    print(f"by_language:  {s.get('by_language')}")
    errs = s.get("errors") or []
    print(f"errors:       {len(errs)}")
    for e in errs[:10]:
        print(f"  - {e}")


def cmd_preview(args):
    session = _session()
    try:
        run = run_preview(session, _org_id(session), _dataset(session, args.slug))
        session.commit()
        _print_summary(run)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def cmd_commit(args):
    session = _session()
    try:
        run = run_commit(session, _org_id(session), uuid.UUID(args.run_id))
        session.commit()
        print(f"committed run {run.id}, phase={run.phase.value}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def cmd_rollback(args):
    session = _session()
    try:
        run = run_rollback(session, uuid.UUID(args.run_id))
        session.commit()
        print(f"rolled back run {run.id}, phase={run.phase.value}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def cmd_run(args):
    session = _session()
    try:
        run = run_preview(session, _org_id(session), _dataset(session, args.slug))
        session.commit()
        _print_summary(run)
        run = run_commit(session, _org_id(session), run.id)
        session.commit()
        print(f"committed run {run.id}, phase={run.phase.value}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="app.etl.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preview"); p.add_argument("slug"); p.set_defaults(func=cmd_preview)
    c = sub.add_parser("commit"); c.add_argument("run_id"); c.set_defaults(func=cmd_commit)
    r = sub.add_parser("rollback"); r.add_argument("run_id"); r.set_defaults(func=cmd_rollback)
    rn = sub.add_parser("run"); rn.add_argument("slug"); rn.set_defaults(func=cmd_run)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/etl/test_cli.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/etl/cli.py backend/tests/etl/test_cli.py
git commit -m "feat(etl): CLI (preview/commit/rollback/run)"
```

---

### Task 11: End-to-end import of real osg10 + verification

**Files:**
- Test: `backend/tests/etl/test_e2e_osg10.py`
- No new source files.

**Interfaces:**
- Consumes: everything from Tasks 1–10.

- [ ] **Step 1: Write the failing test**

`backend/tests/etl/test_e2e_osg10.py`:
```python
from datetime import date
from pathlib import Path

from sqlalchemy import select, func

from app.db.seed import run_seed
from app.etl.runner import run_commit, run_preview
from app.models.auth import Organization
from app.models.etl import EtlDataset, QuestionExternalKey
from app.models.question import Question

REPO_ROOT = Path(__file__).resolve().parents[3]
OSG10 = REPO_ROOT / "docs" / "questions" / "osg10"


def test_e2e_import_osg10(db_session):
    run_seed(db_session)
    ds = db_session.execute(select(EtlDataset).filter_by(slug="osg10")).scalar_one()
    ds.source_path = str(OSG10)  # point at real repo dataset
    db_session.flush()
    org_id = db_session.execute(select(Organization)).scalar_one().id

    run = run_preview(db_session, org_id, ds)
    assert run.preview_summary["would_create"] == 840
    assert db_session.execute(select(Question)).scalars().all() == []  # preview writes nothing

    committed = run_commit(db_session, org_id, run.id)
    assert committed.phase.value == "committed"

    assert db_session.execute(select(func.count(Question.id))).scalar() == 840
    assert db_session.execute(select(func.count(QuestionExternalKey.id))).scalar() == 840

    en = db_session.execute(select(func.count(Question.id)).filter_by(language="en")).scalar()
    zh = db_session.execute(select(func.count(Question.id)).filter_by(language="zh")).scalar()
    assert en == 420 and zh == 420


def test_e2e_reimport_is_idempotent(db_session):
    run_seed(db_session)
    ds = db_session.execute(select(EtlDataset).filter_by(slug="osg10")).scalar_one()
    ds.source_path = str(OSG10)
    db_session.flush()
    org_id = db_session.execute(select(Organization)).scalar_one().id

    run = run_preview(db_session, org_id, ds)
    run_commit(db_session, org_id, run.id)
    run2 = run_preview(db_session, org_id, ds)
    committed2 = run_commit(db_session, org_id, run2.id)

    assert db_session.execute(select(func.count(Question.id))).scalar() == 840
    assert committed2.preview_summary is not None  # committed run retains summary
```

- [ ] **Step 2: Run test to verify it fails (or passes if all prior tasks done)**

Run: `cd backend && python -m pytest tests/etl/test_e2e_osg10.py -v`
Expected: PASS (2 tests) — exercises the real 420-question dataset.

- [ ] **Step 3: Run the full test suite + drift check**

Run:
```bash
cd backend && python -m pytest -v
```
Expected: ALL PASS, including `test_no_autogenerate_drift`.

- [ ] **Step 4: Manual smoke — import via CLI against the dev DB**

Apply migration + seed to the dev DB, then run the import:
```bash
cd backend && alembic upgrade head
cd backend && python -m app.db.seed
cd backend && python -m app.etl.cli run osg10
```
Expected: summary prints `would_create: 840`, then `committed run ... phase=committed`. (Note: the seed sets `source_path="docs/questions/osg10"` which is relative — the CLI/runner resolves it relative to CWD, so run from the `backend/` dir with the path adjusted, OR set `ds.source_path` to an absolute path. If the relative path fails, run from repo root: `cd /home/john/cissp_exam && python -m app.etl.cli run osg10` — but the `app` package is under `backend/`. Resolution: the CLI must resolve `source_path` relative to the repo root, not CWD. **Add to `DatasetReader` a fallback: if the path does not exist, try resolving relative to the repo root (two levels up from `backend/`).** Update `extract.py` `_content_hash`/`read` to use `self.path = Path(dataset_path)` and in `__init__` add: `if not self.path.exists(): repo_root = Path(__file__).resolve().parents[3]; alt = repo_root / dataset_path; if alt.exists(): self.path = alt`. This makes both CLI-from-`backend/` and tests work.)

Apply that `__init__` path-resolution edit to `backend/app/etl/extract.py` `DatasetReader.__init__` (Task 4's file) before the manual smoke.

- [ ] **Step 5: Verify backend health still ok**

Run:
```bash
docker compose up -d --build
curl http://localhost:8000/health
curl http://localhost:8000/api/etl/datasets
```
Expected: `/health` returns `{"status":"ok","db":"ok","redis":"ok"}`; `/api/etl/datasets` lists `osg10`.

- [ ] **Step 6: Update CLAUDE.md**

Update `backend/app/services/cat_engine.py does not exist yet` section and add an "ETL pipeline" bullet under "What exists now": the ETL module exists and osg10 imports via CLI/API. Note `app/api/etl.py` is the first business router (unauthenticated until auth sub-project).

- [ ] **Step 7: Commit**

```bash
git add backend/tests/etl/test_e2e_osg10.py backend/app/etl/extract.py CLAUDE.md
git commit -m "feat(etl): end-to-end osg10 import + path resolution + CLAUDE.md update"
```

---

## Self-Review

**1. Spec coverage:**
- §2 Data model & migration → Tasks 1, 2, 3. ✓
- §3 Extract → Task 4. ✓
- §4 Transform → Task 5. ✓
- §5 Load → Task 6. ✓
- §6 Runner (preview/commit/rollback, drift) → Task 7. ✓
- §7 CLI → Task 10. ✓
- §8 HTTP API → Task 9. ✓
- §9 Chapter→domain seed → Task 8. ✓
- §10 Testing → tests embedded in each task + Task 11 e2e. ✓
- §11 Cross-cutting rules → honored in load (revision snapshot, savepoint, audit, license unconfirmed, idempotent key, tenant scoping, global keys/mappings), migration (native enum drop). ✓
- §12 File inventory → all files appear in tasks. ✓

**Gaps found & addressed:**
- The CLI's `source_path` resolution (relative vs absolute) was a latent gap — addressed in Task 11 Step 4 with a path-resolution fallback in `DatasetReader.__init__`.
- Domain name mismatch (`Identity and Access Management (IAM)` suffix) — addressed in Task 8 by mapping on `number`, not `name`.

**2. Placeholder scan:** No TBD/TODO-as-placeholder. The only `# TODO(auth)` markers are the deliberate, spec-sanctioned unauthenticated-stub markers (spec §1, §8), each accompanied by working fallback code. ✓

**3. Type consistency:** `DatasetReader.read()` returns `(list[RawQuestion], list[ExtractError], str)` — used consistently in runner Task 7. `transform(raw, language, pending_translation_ids=None)` — consistent. `apply_load(...)`/`apply_dry_run(...)` signatures — consistent between Task 6 (def) and Task 7 (call). `run_preview(session, org_id, dataset, initiated_by_id=None)`, `run_commit(session, org_id, run_id)`, `run_rollback(session, run_id)` — consistent between Task 7 and Tasks 9/10. `CleanedQuestion` fields match between Task 5 (def) and Task 6 (consume). ✓
