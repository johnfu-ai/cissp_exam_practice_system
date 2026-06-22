# Sub-project C: Question Bank CRUD — Design Spec

> Source of truth: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` (§6.4 FR-Q-*, §9.5 API surface, §10 import validation). Auth & RBAC (sub-project B) is merged and provides `require_permission`, `CurrentUser`, `get_active_org_id`.

## Goal

Deliver the question-bank management API: create/read/update/soft-delete questions, their status lifecycle and review workflow, revision history, and learner correction feedback — plus the taxonomy READ endpoints needed to drive question creation and filtering. This makes the bank manageable and selectable for practice (sub-project E).

## Scope

**In scope (P0/P1):**
- FR-Q-01 create / edit / soft-delete questions
- FR-Q-02 status lifecycle: `draft → pending_review → published → needs_revision → archived`
- FR-Q-03 single + multiple choice full data model (options, correct flags, explanation)
- FR-Q-04 true_false + scenario types (data model + validation)
- FR-Q-05 ordering / drag_drop / hotspot data structure reserved via `prompt_items` JSONB
- FR-Q-06 revision history (who changed what, when) via `QuestionRevision`
- FR-Q-07 correction feedback (unclear explanation / suspected wrong answer / ambiguous stem / copyright / other)
- Taxonomy READ endpoints (§9.5): `GET /api/domains`, `GET /api/books`, `GET /api/books/{id}/chapters`, `GET /api/knowledge-points`

**Deferred to later sub-projects:**
- FR-Q-08 quality statistics (error/controversy/exposure/avg-time) — needs practice data → sub-projects E/H
- FR-IMP-01..09 interactive import (CSV/XLSX/JSON upload + Markdown paste + field mapping + preview) and `GET /api/questions/export` — separate import sub-project; batch ETL already covers OSG ingestion
- Taxonomy WRITE/admin (FR-TAX-02..06) — sub-project D

## Architecture

Service-layer backend (per CLAUDE.md): route handlers in `app/api/` delegate to service modules in `app/services/` that own logic + DB. All queries are ORM/parameterized. Content tables are `organization_id`-scoped (tenant); taxonomy (`ExamDomain`, `KnowledgePoint`) is GLOBAL. Soft delete only, via `not_deleted(Question)`.

### New model: `QuestionFeedback`

Learner-reported correction feedback (FR-Q-07). Lives in `app/models/question.py` + a migration.

```
QuestionFeedback(UUIDPrimaryKey, TenantScopedMixin, TimestampMixin, SoftDeleteMixin, Base)
  question_id   FK questions.id ON DELETE CASCADE, NOT NULL
  reporter_id   FK users.id, nullable
  feedback_type Enum(QuestionFeedbackType) NOT NULL   -- new native PG enum
  comment       Text, nullable
  status        Enum(QuestionFeedbackStatus) NOT NULL DEFAULT 'open'  -- new native PG enum
```

Two new enums in `app/models/enums.py` (created as `CREATE TYPE` in the migration, dropped in `downgrade()`):

```
QuestionFeedbackType: unclear_explanation | suspected_wrong_answer | ambiguous_stem | copyright_issue | other
QuestionFeedbackStatus: open | resolved | wont_fix
```

`QuestionRevision` already exists (created in the ETL migration) — reused as-is.

### Service layer

`app/services/question.py`:

- `create_question(session, *, org_id, actor_id, payload: QuestionCreateIn) -> Question`
  - Validates option rules (below). Builds `Question` (status=draft, version=1), `QuestionOption` rows, optional `Explanation`, and `QuestionMapping` rows (domain/chapter/knowledge_point/tag). Commits nothing (caller commits). Writes `QuestionRevision` #1 (initial snapshot). Logs `AuditAction.edit`.
- `get_question(session, question_id) -> Question` — raises `LookupError` (→404) if missing or soft-deleted.
- `list_questions(session, *, org_id, filters: QuestionFilters, page, size) -> tuple[list[Question], int]` — tenant-scoped + `not_deleted`. Filters: `domain_id`, `book_id`, `chapter_id`, `knowledge_point_id`, `tag_id`, `question_type`, `status`, `difficulty`, `language`, `search` (stem ILIKE). Ordered by `created_at desc`. Returns (items, total).
- `update_question(session, *, question_id, actor_id, payload: QuestionUpdateIn) -> Question`
  - Partial update. If any content field changed (stem, options, explanation, mappings, type, difficulty, language), writes a `QuestionRevision` snapshot of the **pre-edit** state, then bumps `version`. Re-validates option rules when options/type change. Logs `AuditAction.edit`.
- `delete_question(session, *, question_id, actor_id)` — soft delete (`deleted_at = now()`). Logs `AuditAction.delete`.
- `submit_review(session, *, question_id, actor_id, action: ReviewAction, comment: str | None) -> Question` — state-machine transitions (below). Logs `publish` on approve, `archive` on archive.
- `list_revisions(session, question_id) -> list[QuestionRevision]` — ascending by `revision_number`.
- `create_feedback(session, *, org_id, question_id, reporter_id, payload: FeedbackIn) -> QuestionFeedback` — status=open. Validates question exists + not deleted.
- `list_feedback(session, *, question_id) -> list[QuestionFeedback]` — newest first.

`app/services/taxonomy.py` (read-only):
- `list_domains(session) -> list[ExamDomain]` — GLOBAL, ordered by `number`.
- `list_books(session, *, org_id) -> list[Book]` — tenant-scoped.
- `list_chapters(session, *, book_id, org_id) -> list[Chapter]` — verifies book belongs to org, ordered by `order_index`.
- `list_knowledge_points(session) -> list[KnowledgePoint]` — GLOBAL.

### Review state machine

```
draft          --submit-->          pending_review
pending_review --approve-->         published
pending_review --request_changes--> needs_revision
needs_revision --submit-->          pending_review
published      --archive-->         archived
archived       --restore-->         draft
<any>          --archive-->         archived
```

`ReviewAction` enum (Pydantic, not DB): `submit | approve | request_changes | archive | restore`.
Permission mapping: `submit`/`request_changes`/`restore` → `question:write`; `approve`/`archive` → `question:publish`. Illegal transitions → `ValueError` (→409).

### Validation rules (PRD §6.4, §10.2)

- `single_choice`: exactly 1 correct option.
- `multiple_choice`: ≥ 2 correct options.
- `true_false`: exactly 2 options, exactly 1 correct.
- `scenario`: stored as single_choice-like (one correct) for MVP; `prompt_items` may carry scenario context.
- Options count: 2–8 (true_false fixed at 2).
- `stem` non-empty; `question_type` valid enum.
- `domain_id`/`chapter_id`/`knowledge_point_id`/`tag_id`, if provided, must reference existing rows (domain/kp global; chapter tenant-scoped via its book).
- Violations raise `ValueError` with a message → HTTP 422 from the route.

### Schemas (`app/schemas/question.py`)

`OptionIn` (content, content_format?, is_correct, order_index?, explanation?), `OptionOut`.
`ExplanationIn` (correct_answer_rationale, key_point_summary?, further_reading?).
`QuestionCreateIn` (question_type, stem, stem_format?, difficulty?, language?, source?, license_status?, prompt_items?, options: list[OptionIn], explanation?: ExplanationIn, domain_id?, chapter_id?, knowledge_point_id?, tag_ids?: list[uuid]).
`QuestionUpdateIn` (all optional, same fields).
`QuestionOut` (id, question_type, stem, stem_format, difficulty, language, status, source, license_status, version, prompt_items, created_at, updated_at, options: list[OptionOut], explanation?: ExplanationOut, mappings: {domain_id?, chapter_id?, knowledge_point_id?, tag_ids}).
`QuestionListItem` (id, question_type, stem_preview, status, difficulty, language, domain_id?, created_at) — lightweight for list view.
`ReviewActionIn` (action: ReviewAction, comment?).
`FeedbackIn` (feedback_type, comment?), `FeedbackOut`.
`RevisionOut` (revision_number, edited_by_id?, edited_at, change_summary?, snapshot).

Taxonomy schemas (`app/schemas/taxonomy.py`): `DomainOut`, `BookOut`, `ChapterOut`, `KnowledgePointOut`.

### API (`app/api/questions.py`, prefix `/api/questions`; `app/api/taxonomy.py`)

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/api/questions` | `question:read` | list, filters via query params, `page`/`size` (default 1/20, max 100) |
| POST | `/api/questions` | `question:write` | create |
| GET | `/api/questions/{id}` | `question:read` | detail incl. options/explanation/mappings |
| PUT | `/api/questions/{id}` | `question:write` | partial update |
| DELETE | `/api/questions/{id}` | `question:write` | soft delete |
| POST | `/api/questions/{id}/review` | `question:write` or `question:publish` (by action) | state transition |
| GET | `/api/questions/{id}/revisions` | `question:read` | revision history |
| POST | `/api/questions/{id}/feedback` | `question:read` | learner correction feedback |
| GET | `/api/questions/{id}/feedback` | `question:read` | list feedback (editors/admins) |
| GET | `/api/domains` | `question:read` | GLOBAL domains |
| GET | `/api/books` | `question:read` | tenant books |
| GET | `/api/books/{id}/chapters` | `question:read` | chapters of a book |
| GET | `/api/knowledge-points` | `question:read` | GLOBAL knowledge points |

`require_permission` is applied per-route via `Depends`. `current.org_id` / `current.user.id` flow into services. Routes catch `LookupError`→404, `ValueError`→422 (validation) or 409 (illegal transition), and call `session.commit()` after successful mutations.

### Audit

- create / update → `AuditAction.edit`, `entity_type="question"`, `entity_id=str(id)`.
- approve → `AuditAction.publish`.
- archive → `AuditAction.archive`.
- delete → `AuditAction.delete`.

## Testing (TDD, real `cissp_test` DB)

Service tests (`tests/test_question_service.py`):
- create valid single/multiple/true_false; rejects single with 0 or 2 correct, multi with 1 correct, true_false with 3 options.
- get raises on missing / soft-deleted.
- list: pagination, each filter, tenant scoping (other org's questions invisible), `not_deleted` excludes deleted.
- update bumps version + writes a revision capturing pre-edit state; no-op update does not bump.
- soft delete excludes from list/get.
- review: each legal transition; illegal transition raises; permission mapping enforced at API layer.
- feedback: create + list; create on deleted question raises.

API tests (`tests/test_question_api.py`, `tests/test_taxonomy_api.py`): reuse the auth-rbac test pattern — register user, promote to role, mint token, pass headers. Cover 401 (no token), 403 (wrong role), 200 happy paths, 422 validation, 409 illegal transition, 404.

Migration test: `tests/test_migrations.py` already runs autogenerate-drift; after adding the model + migration, drift must stay at zero.

## Out-of-scope reminders

- Do not implement practice/exam selection logic (sub-project E+) — only ensure `published` is the selectable status convention.
- Do not compute FR-Q-08 stats (no practice data yet).
- Do not add taxonomy write endpoints (sub-project D).
- Interactive import + export deferred.
