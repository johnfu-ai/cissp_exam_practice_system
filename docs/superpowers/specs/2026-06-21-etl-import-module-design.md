# ETL Import Module (osg10) — Design Spec

**Date:** 2026-06-21
**Sub-project:** B-1 — ETL pipeline + CLI + HTTP API for importing `docs/questions/osg10/`
**PRD reference:** `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` §6.3.2, §9.4, §9.5, §9.6, §10.3, §10.4
**Goal:** Make the application runnable with real question data by building an Extract/Transform/Load pipeline that ingests the bilingual OSG v10 dataset (420 questions → 840 rows) idempotently into the question bank, driven by a CLI and an HTTP API.

---

## 1. Scope & Locked Decisions

This sub-project delivers the **ETL pipeline** (`app/etl/`), a **CLI**, and an **HTTP API**. Four design decisions were made during brainstorming and govern everything below:

| # | Decision | Choice |
|---|----------|--------|
| 1 | Scope | Pipeline (`app/etl/`) + CLI + HTTP API. Endpoints are **unauthenticated stubs** until the auth/JWT sub-project lands; each handler carries a `# TODO(auth)` marker and resolves `org_id` from the seeded personal org, `initiated_by_id=None`. |
| 2 | Bilingual storage | **Two `Question` rows per source question** (`language='en'` and `'zh'`), linked by a shared `external_id` via `QuestionExternalKey`. Existing single-Text `stem`/`content` columns are **not changed** for bilingual purposes (a new JSONB column is added only for `prompt_items`). |
| 3 | `matching` type | Normalize to **`single_choice`** (each matching record has exactly 1 correct key). `prompt_items` stored in a new `questions.prompt_items` JSONB column. `needs_revision` flagged. No enum change. |
| 4 | Chapter→domain | **Seeded `ChapterDomainMapping`** (GLOBAL) carries the OSG v10 21-chapter→8-domain assignment; load applies it. Editable later via `/api/etl/mappings`. |

**Load strategy (Approach A):** Transform is a set of pure functions producing a deterministic load plan. Dry-run runs extract+transform and persists a read-only `preview_summary`; commit **re-runs** extract+transform (idempotent, safe) and applies the load in one transaction. No staging table, no DB state between phases. A content hash of the source files is recorded at preview time and checked at commit to detect drift.

### Out of scope (later sub-projects)
- Auth/JWT and real identity injection into the API handlers.
- CSV/XLSX/JSON (non-JSONL) extractors — only the JSONL+manifest extractor is built now; the `DatasetReader` interface leaves room for them.
- Post-commit transactional rollback (a committed import is corrected via edits + soft-delete).
- The interactive upload import path (§6.3.1 FR-IMP-*), frontend ETL UI.

---

## 2. Data Model & Migration

### 2.1 New models — `app/models/etl.py` (registered in `app/models/__init__.py`)

**`EtlDataset`** *(tenant-scoped, content table)* — one row per dataset directory.
- `slug: str` unique (e.g. `osg10`)
- `name: str`
- `source_path: str` — relative to a configured datasets root (e.g. `docs/questions/osg10`)
- `format: ImportFormat` — `json` for the JSONL+manifest format
- `total_questions: int`
- `languages: list[str]` — PostgreSQL `ARRAY(String)` (`['en','zh']`)
- `notes: str | None`
- Mixins: `UUIDPrimaryKey`, `TenantScopedMixin`, `TimestampMixin`

**`EtlRun`** *(tenant-scoped)* — one execution of a dataset.
- `dataset_id: UUID` FK `etl_datasets.id`
- `import_job_id: UUID` FK `import_jobs.id` (existing `ImportJob` tracks row-level accounting)
- `phase: EtlRunPhase` enum (`preview` / `committed` / `rolled_back`)
- `preview_summary: JSONB | None` — counts by action/type/language, error list, sample ops, content hash
- `committed_at: datetime | None`
- Mixins: `UUIDPrimaryKey`, `TenantScopedMixin`, `TimestampMixin`

**`QuestionExternalKey`** *(GLOBAL — not tenant-scoped)* — idempotency anchor. One row per `Question` (840 for osg10).
- `dataset_slug: str`
- `external_id: str` (e.g. `osg-v10-ch01-q01`)
- `language: str` (`en`/`zh`)
- `question_id: UUID` FK `questions.id`
- Unique constraint `(dataset_slug, external_id, language)`
- Mixins: `UUIDPrimaryKey`, `TimestampMixin` (no tenant — source-level fact)

**`ChapterDomainMapping`** *(GLOBAL)* — seeded OSG chapter→domain.
- `dataset_slug: str`
- `chapter_number: int` (1–21)
- `domain_id: UUID | None` FK `exam_domains.id`
- `chapter_title: str` (denormalized for readability)
- Unique constraint `(dataset_slug, chapter_number)`
- Mixins: `UUIDPrimaryKey`, `TimestampMixin`

### 2.2 New enum — `app/models/enums.py`

```python
class EtlRunPhase(str, enum.Enum):
    preview = "preview"
    committed = "committed"
    rolled_back = "rolled_back"
```

### 2.3 Existing model change

`Question` (`app/models/question.py`) gains one nullable column:
```python
prompt_items: Mapped[list | None] = mapped_column(JSONB, nullable=True)
```
Stores the matching context (`prompt_items` array) for the 3 normalized matching questions; `NULL` for all others.

### 2.4 Migration

One Alembic revision (`alembic revision --autogenerate -m "etl models and prompt_items"`):
- `CREATE TYPE etl_run_phase` + the 4 tables.
- `ALTER TABLE questions ADD COLUMN prompt_items JSONB`.
- `downgrade()` explicitly `DROP TYPE etl_run_phase` (per the existing native-ENUM-drop pattern — autogen `drop_table` does not drop types).

The autogenerate no-drift test (`tests/test_migrations.py`) must stay green. The existing filters for `uq_users_email_lower` and `_test_*` tables remain.

---

## 3. Extract — `app/etl/extract.py`

**Responsibility:** read a dataset directory into typed `RawQuestion` dataclasses. Pure I/O + parsing, no business logic, no DB.

### 3.1 Dataclasses (the extract→transform contract)

```python
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
    type: str                       # "single_choice" | "multiple_choice" | "matching"
    stem: Bilingual
    options: list[RawOption]
    correct_keys: list[str]
    explanation: Bilingual
    meta: dict                      # choose_all, matching, issues, zh_source, zh_issues
    prompt_items: list[RawPromptItem] | None   # matching only

@dataclass
class ExtractError:
    line_no: int | None
    external_id: str | None
    reason: str
```

### 3.2 `DatasetReader`

```python
class DatasetReader:
    def __init__(self, dataset_path: str | Path): ...
    def read(self) -> tuple[list[RawQuestion], list[ExtractError], str]:
        # returns (raws, errors, content_hash)
```

- Reads `manifest.json`; validates `total_questions` (warns on mismatch, recorded in errors, does not abort).
- Streams `questions.jsonl` line-by-line; each line parsed into `RawQuestion`.
- **`zh_overrides.json` is treated as already-merged** — the JSONL records already contain merged `{en,zh}` fields (verified against `osg-v10-ch01-q07`). The reader records the override file's presence in the summary for provenance but does not re-apply it. (`translate_queue.json`, if non-empty, contributes `translation_pending` issues at transform time; it is `[]` for osg10.)
- Computes a content hash (sha256 over `manifest.json` + `questions.jsonl` bytes) returned for the runner's drift check.
- **Error isolation:** a malformed JSON line or missing required field raises an `ExtractError` collected into the errors list; the batch continues. Returns `(raws, errors, content_hash)`.

### 3.3 Tests — `tests/etl/test_extract.py`
A `tests/etl/fixtures/mini/` directory with manifest + 4 JSONL lines (single, multiple, matching, malformed). Asserts correct typing, malformed line lands in `errors` not `raws`, manifest mismatch flagged, content hash stable.

---

## 4. Transform — `app/etl/transform.py`

**Responsibility:** pure functions turning `RawQuestion` into `CleanedQuestion` (a per-language load-plan record) plus validation. No DB, no I/O. **Deterministic** — same raw in twice = same cleaned out. This is what makes Approach A safe.

### 4.1 Dataclass (transform→load contract)

```python
@dataclass
class CleanedOption:
    key: str
    content: str                    # Text for this language
    is_correct: bool

@dataclass
class CleanedQuestion:
    external_id: str
    language: str                   # "en" | "zh"
    question_type: QuestionType     # normalized
    stem: str
    options: list[CleanedOption]
    explanation: str
    prompt_items: list | None       # JSONB-serializable; matching only, else None
    source_chapter: int
    source_chapter_title: str
    difficulty: int                 # default 3 (medium)
    issues: list[str]
    needs_revision: bool
```

### 4.2 Functions

```python
def validate(raw: RawQuestion) -> list[str]:
    # required fields present; correct_keys ⊆ option keys;
    # single_choice has exactly 1 correct key; multiple_choice ≥2.
    # (matches PRD FR-ETL-06)
    # returns issues (does not raise)

def transform(raw: RawQuestion, language: str, pending_translation_ids: set[str] | None = None) -> CleanedQuestion:
    # one cleaned record per language; caller invokes twice (en, zh)
```

### 4.3 Normalization rules

1. **Type:** `matching` → `single_choice`. `single_choice`/`multiple_choice` pass through.
2. **Bilingual split:** `transform(raw, "en")` takes `stem.en`, each `option.text.en`, `explanation.en`; `"zh"` takes `.zh`. If a `.zh` field is missing/empty for the zh record → `needs_revision=True`, fall back to the `en` text (row not blank), record `"missing_zh"` issue.
3. **Options:** `is_correct = key in raw.correct_keys`. Order preserved.
4. **prompt_items:** carried through only when `raw.type == "matching"`; serialized to JSONB-serializable list. `None` otherwise.
5. **Defaults:** `difficulty = 3`. `issues` aggregates `meta.issues` + `meta.zh_issues`; if the id is in `pending_translation_ids`, add `"translation_pending"`.

**Dedup is NOT in transform** — it is a load-time concern (needs DB lookup). Transform only produces the plan. This keeps transform pure and DB-free.

### 4.4 Tests — `tests/etl/test_transform.py`
Pure-function, no DB. One test per rule: matching→single_choice with prompt_items; bilingual split; missing-zh fallback + needs_revision; is_correct from correct_keys; single_choice validation flags >1 correct; difficulty default 3.

---

## 5. Load — `app/etl/load.py`

**Responsibility:** take `list[CleanedQuestion]`, apply create-or-update against the DB within a single transaction. Owns all DB access and dedup.

### 5.1 Result types

```python
@dataclass
class LoadResult:
    created: int
    updated: int
    unchanged: int
    errors: list[dict]              # [{external_id, language, reason}]

@dataclass
class DryRunSummary:
    would_create: int
    would_update: int
    unchanged: int
    errors: list[dict]
    by_type: dict
    by_language: dict
```

### 5.2 `apply_load`

```python
def apply_load(session, org_id, dataset_slug, import_job_id, cleaned: list[CleanedQuestion]) -> LoadResult
```

Per cleaned record:
1. **Dedup lookup:** `QuestionExternalKey` by `(dataset_slug, external_id, language)`.
   - No match → **create:** insert `Question` (org-scoped), `QuestionOption`s, `Explanation`, `QuestionExternalKey`, `QuestionMapping` (chapter_id + domain_id). `created += 1`.
   - Match → **update:** load existing `Question`. Diff current stem/options/explanation against cleaned. Identical → `unchanged` (skip, no revision). Different → update row, write `QuestionRevision` with the **old** snapshot (historical integrity via `snapshot_question()`), bump `version`. `updated += 1`.
2. **Status:** `status = needs_revision if cleaned.needs_revision else draft`. `license_status` stays `unconfirmed` (unauthorized questions never auto-publish).
3. **Book/Chapter resolution:** `Book(title="CISSP OSG", edition="10")` within org (create-once, cached); `Chapter(book_id, order_index=source_chapter)` (create-once, cached). Batch-cached in dicts.
4. **Domain mapping:** `ChapterDomainMapping(dataset_slug, chapter_number=source_chapter)` → `domain_id` on `QuestionMapping`. None + issue if missing (defensive).
5. **Error isolation:** each record wrapped in `session.begin_nested()` (SAVEPOINT); exception → rollback that savepoint, record in `errors`, continue. Batch transaction stays alive.
6. **Commit control:** `apply_load` only **stages**; the runner calls `session.commit()`. On success → `ImportJob` counts finalized; on failure → whole batch rolls back.

### 5.3 `apply_dry_run`

```python
def apply_dry_run(session, org_id, dataset_slug, cleaned: list[CleanedQuestion]) -> DryRunSummary
```
Read-only diff (dedup lookups, classify `would_create`/`would_update`/`unchanged`/`error`). No `Question` writes, no revisions. Backs the preview.

### 5.4 Tests — `tests/etl/test_load.py`
DB tests on `cissp_test`. Create flow (new key → all rows + org-scoped). Update flow (existing key, changed stem → version bumps, `QuestionRevision` with old snapshot). Unchanged flow (no revision). Domain mapping applied. Savepoint isolation (one bad record → in `errors`, batch survives).

---

## 6. Runner — `app/etl/runner.py`

**Responsibility:** orchestrate extract → transform → load across preview/commit. Owns the session lifecycle and writes `EtlRun` / `ImportJob`.

### 6.1 `run_preview`

```python
def run_preview(session, org_id, dataset: EtlDataset, initiated_by_id=None) -> EtlRun
```
1. Create `ImportJob(format=json, source=dataset.source_path, license_status=unconfirmed, status=previewing, initiated_by_id)`.
2. Create `EtlRun(dataset_id, import_job_id, phase=preview)`.
3. `raws, extract_errors, content_hash = DatasetReader(dataset.source_path).read()`.
4. For each raw, for each language in `dataset.languages`: collect `validate(raw)` issues, then `transform(raw, lang)` → `CleanedQuestion`. Collect per-record errors (don't abort).
5. `summary = apply_dry_run(session, org_id, dataset.slug, cleaned)`.
6. Merge `extract_errors` + transform errors into `summary.errors`. Set `EtlRun.preview_summary = {**summary, content_hash}`; `ImportJob.status=previewing`, `total_rows=len(cleaned)`, `error_count`.
7. Commit. Return `EtlRun`.

### 6.2 `run_commit`

```python
def run_commit(session, org_id, run_id) -> EtlRun
```
1. Load `EtlRun`; assert `phase == preview`.
2. **Re-run extract + transform** (Approach A — deterministic, idempotent). Rebuild the same `cleaned` list.
3. **Drift check:** compare the fresh `content_hash` to the one stored in `preview_summary`. If mismatch → raise `EtlDriftError` (the dataset changed since preview; re-preview required).
4. `result = apply_load(session, org_id, dataset.slug, import_job_id, cleaned)`.
5. Set `EtlRun.phase=committed`, `committed_at=now`; `ImportJob.status = completed if no errors else partial`, `success_count`, `error_count`, `error_report=result.errors`.
6. `log_audit(session, action=import_action, ...)` (cross-cutting audit rule).
7. Commit. Return `EtlRun`.

### 6.3 `run_rollback`

```python
def run_rollback(session, run_id) -> EtlRun
```
Only valid before commit. Marks `EtlRun.phase=rolled_back`, `ImportJob.status=failed`. Preview wrote no live rows (dry-run is read-only), so rollback is a status flip — nothing to undo in the question tables.

### 6.4 Tests — `tests/etl/test_runner.py`
End-to-end on `cissp_test`: `run_preview` summary has correct `would_create`, writes no `Question`; `run_commit` writes 840 rows; second `run_commit` of same dataset idempotent (all `unchanged`); `run_rollback` flips status, writes no rows; drift check raises when files change between preview and commit.

---

## 7. CLI — `app/etl/cli.py` (runnable as `python -m app.etl.cli`)

Mirrors the existing `python -m app.db.seed` pattern. Resolves the dataset by slug against the seeded `EtlDataset` table; creates its own session via `app.db.session`.

```
python -m app.etl.cli preview osg10          # dry-run, print summary
python -m app.etl.cli commit <run_id>        # commit a previewed run
python -m app.etl.cli rollback <run_id>      # discard a previewed run
python -m app.etl.cli run osg10              # preview + commit in one step
```

`preview`/`run` print a human-readable summary (counts by action/type/language, error list). This is how osg10 gets imported in dev/CI without the frontend or auth — directly satisfying "make the application runnable with real data."

---

## 8. HTTP API — `app/api/etl.py` (registered in `app/main.py` under `/api/etl`)

Thin handlers delegating to `runner.*` (service-layer rule: no business logic in routes). **Unauthenticated stubs** — `org_id` from the seeded personal org, `initiated_by_id=None`, each handler marked `# TODO(auth): replace with real org/user from JWT`.

| Method | Path | Behavior |
|--------|------|----------|
| `GET` | `/api/etl/datasets` | list registered `EtlDataset` |
| `GET` | `/api/etl/datasets/{slug}` | one dataset |
| `POST` | `/api/etl/runs` | body `{dataset_slug}` → `run_preview`, returns `EtlRun` (run_id + preview_summary) |
| `GET` | `/api/etl/runs/{run_id}` | run status + summary |
| `POST` | `/api/etl/runs/{run_id}/commit` | `run_commit` |
| `POST` | `/api/etl/runs/{run_id}/rollback` | `run_rollback` |
| `GET/POST/PUT/DELETE` | `/api/etl/mappings` | CRUD on `ChapterDomainMapping` |

The existing `/health` endpoint is untouched.

### Tests — `tests/etl/test_api_etl.py`
FastAPI `TestClient`: `POST /api/etl/runs` returns run with preview_summary; `GET /runs/{id}`; `POST /runs/{id}/commit` commits; `GET /datasets` lists seeded osg10.

---

## 9. Chapter→Domain Mapping Seed

The OSG v10 is organized around the 8 CISSP domains. The 21-chapter→domain assignment (canonical OSG structure):

| Domain | Chapters |
|--------|----------|
| 1 — Security and Risk Management | 1, 2, 3, 4 |
| 2 — Asset Security | 5 |
| 3 — Security Architecture and Engineering | 6, 7, 8, 9, 10 |
| 4 — Communication and Network Security | 11, 12 |
| 5 — Identity and Access Management | 13, 14 |
| 6 — Security Assessment and Testing | 15 |
| 7 — Security Operations | 16, 17, 18, 19 |
| 8 — Software Development Security | 20, 21 |

### Seed mechanism — extend `app/db/seed.py`
Guarded by a `SchemaMeta.seed_version` bump (same idempotent pattern as the existing seed):
1. Upsert `EtlDataset` for `osg10` (`slug='osg10'`, source_path=`docs/questions/osg10`, format=json, total_questions=420, languages=['en','zh']).
2. Upsert 21 `ChapterDomainMapping` rows for `osg10`, joining to the already-seeded `ExamDomain` rows by domain order/name.

The exact seeded `ExamDomain` names/order will be verified against the taxonomy seed during implementation so the FK joins correctly. The mapping is data — editable later via `/api/etl/mappings`.

### Tests — extend `tests/test_seed.py`
Assert the osg10 `EtlDataset` + 21 `ChapterDomainMapping` rows exist after seed; seed is idempotent (re-run → no duplicates).

---

## 10. Testing Strategy (summary)

Real PostgreSQL via `cissp_test`, per-test SAVEPOINT rollback (no SQLite), per the existing conventions.

| File | Covers |
|------|--------|
| `tests/etl/test_extract.py` | `DatasetReader`, fixture dataset, error isolation, content hash |
| `tests/etl/test_transform.py` | pure normalization rules (matching→single_choice, bilingual split, validation) |
| `tests/etl/test_load.py` | create/update/unchanged flows, dedup by external key, savepoint isolation, domain mapping, revision snapshot |
| `tests/etl/test_runner.py` | two-phase lifecycle, idempotency, drift check, rollback |
| `tests/etl/test_api_etl.py` | router endpoints end-to-end (unauthenticated) |
| `tests/test_seed.py` (extend) | osg10 dataset + 21 mappings seeded, idempotent |
| `tests/test_migrations.py` (existing) | no-autogenerate-drift stays green |

---

## 11. Cross-Cutting Rules Honored

- **Service-layer backend:** routes delegate to `runner.*`; no business logic in handlers.
- **Tenant scoping:** `EtlDataset`/`EtlRun` org-scoped; `QuestionExternalKey`/`ChapterDomainMapping` GLOBAL (source-level facts → global taxonomy).
- **Native PostgreSQL ENUMs:** `EtlRunPhase` created as `CREATE TYPE`; `downgrade()` drops it explicitly.
- **UUID PKs** with `gen_random_uuid()`.
- **Historical integrity:** `QuestionRevision` stores the old snapshot before any update (via `snapshot_question()`).
- **Soft delete only:** load never hard-deletes; questions are created/updated.
- **Audit logging:** `log_audit(action=import_action)` on commit.
- **License safety:** `license_status` stays `unconfirmed`; imported questions enter as `draft`/`needs_revision`, never auto-published. Unauthorized questions never enter the shared bank as published.
- **Idempotency:** `(dataset_slug, external_id, language)` unique key; re-runs update only changed rows.

---

## 12. File Inventory

**Create:**
- `backend/app/models/etl.py`
- `backend/app/etl/__init__.py`
- `backend/app/etl/extract.py`
- `backend/app/etl/transform.py`
- `backend/app/etl/load.py`
- `backend/app/etl/runner.py`
- `backend/app/etl/cli.py`
- `backend/app/api/etl.py`
- `backend/alembic/versions/<rev>_etl_models_and_prompt_items.py`
- `backend/tests/etl/__init__.py`
- `backend/tests/etl/fixtures/mini/{manifest.json,questions.jsonl}`
- `backend/tests/etl/test_extract.py`
- `backend/tests/etl/test_transform.py`
- `backend/tests/etl/test_load.py`
- `backend/tests/etl/test_runner.py`
- `backend/tests/etl/test_api_etl.py`

**Modify:**
- `backend/app/models/enums.py` — add `EtlRunPhase`
- `backend/app/models/question.py` — add `Question.prompt_items` JSONB
- `backend/app/models/__init__.py` — register etl models
- `backend/app/main.py` — mount `/api/etl` router
- `backend/app/db/seed.py` — seed osg10 dataset + 21 chapter→domain mappings (+ `SchemaMeta.seed_version` bump)
- `backend/tests/test_seed.py` — assert osg10 seed
