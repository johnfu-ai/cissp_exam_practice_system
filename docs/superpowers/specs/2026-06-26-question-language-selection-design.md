# Question Language Selection & Bilingual Display — Design Spec

> Source of truth: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` v1.1 (2026-06-26) — §6.4 FR-LANG-01..10, §6.5 FR-PRAC-11, §6.6 FR-ANS-10, §6.7 FR-EXAM-07, §6.8 FR-CAT-11, §9.4 data model, §9.5 API surface, §10 import template/validation, §12 MVP scope, §14 acceptance criteria. Builds on the merged practice/exam/CAT/analytics/admin backend and the Next.js frontend.

## Goal

Add bilingual (English / Chinese) question content and a user-selectable language mode (`en` / `zh` / `bilingual`) to the practice and exam experience. Users pick a default mode (saved as a personal preference), override it when creating a session, and toggle it mid-session without losing answers, timing, or progress. Only questions possessing the requested language enter an `en`- or `zh`-mode session; `bilingual` mode shows both languages side-by-side per question with options paired 1:1. The chosen language mode and content are frozen into answer snapshots so history is unaffected by later edits. Question authoring/import lets editors maintain both language versions and check completeness before publish.

## Scope

**In scope (FR-LANG-01..10, P0/P1, plus a P2 admin coverage view):**

- FR-LANG-01 — bilingual storage of stem, every option, and explanation (separate en/zh versions)
- FR-LANG-02 — user language mode `en` | `zh` | `bilingual`
- FR-LANG-03 — default saved as a personal preference; overridable per practice/exam session
- FR-LANG-04 — `en`/`zh` sessions deliver only questions possessing that language
- FR-LANG-05 — `bilingual` shows both languages side-by-side per question, options paired 1:1
- FR-LANG-06 — instant in-runner mode toggle, no loss of answers/timing/progress
- FR-LANG-07 — answer snapshots record the chosen mode and both-language content; later edits don't change history
- FR-LANG-08 — import accepts `*_zh` fields; single-language questions can be supplemented later
- FR-LANG-09 — editor edits/previews en and zh separately; publish validates required-language completeness
- FR-LANG-10 — admin language-coverage query + filter by missing language
- Supporting: FR-PRAC-11, FR-ANS-10, FR-EXAM-07, FR-CAT-11 (session language mode)
- User preferences API: `GET/PUT /api/users/me/preferences`

**Out of scope (explicitly deferred):**

- UI chrome / UI-string i18n (PRD §16 open-question #3 — defers UI-string internationalization; only *question content* is bilingual here)
- 3PL IRT CAT scoring (still rule-driven MVP per §11)
- Additional languages beyond `en`/`zh` (model is generic but only these two are wired)

## Approach chosen

**Approach B — PRD §9.4-faithful `QuestionTranslation` model.** One `Question` row holds structural/canonical fields (type, difficulty, status, correctness key, version, mappings) plus an `available_languages` set; a new `question_translations` table holds per-language content (stem, per-language option content, explanation). The old single-language text columns on `Question`, `QuestionOption`, and the `Explanation` table are retired.

Rejected alternatives:
- **Approach A (two Question rows per language, delivery-time filter)** — already how ETL loads data today, and is the smallest change. Rejected because it breaks FR-LANG-05/06/09 for *manually authored* questions (no `external_id` pairing → cannot show both languages side-by-side, cannot toggle, cannot edit en+zh as one question). PRD v1.1 explicitly superseded the old "two rows" resolution recorded in §16 open-question #9.
- **Approach C (denormalized English on `Question` + translations table)** — dual sources of truth; violates FR-LANG-01 ("separately maintain en/zh") and complicates editing/validation.

## Architecture

Service-layer backend (per CLAUDE.md): routes in `app/api/` delegate to `app/services/` owning logic + DB. Content tables stay `organization_id`-scoped (tenant); taxonomy stays GLOBAL. Soft delete via `not_deleted(Question)`. Native PG enums in `app/models/enums.py`, dropped in migration `downgrade()`. UUID PKs with `gen_random_uuid()`. Historical integrity via snapshots (`snapshot_question()`). Audit on every mutation via `log_audit()`.

### Data model changes

**New table `question_translations`** (in `app/models/question.py`):

```
QuestionTranslation(UUIDPrimaryKey, TimestampMixin, Base)
  question_id   FK questions.id ON DELETE CASCADE, NOT NULL
  language      String(5) NOT NULL            -- 'en' | 'zh'
  stem          Text NOT NULL
  stem_format   Enum(TextFormat) NOT NULL DEFAULT 'markdown'
  correct_answer_rationale  Text NOT NULL
  key_point_summary         Text, nullable
  further_reading           Text, nullable
  options       JSONB NOT NULL                -- [{order_index, content, content_format, explanation}]
  __table_args__ = UniqueConstraint(question_id, language, name="uq_question_translations_qid_lang")
```

`options` JSONB shape (per translation): an array ordered by `order_index`:
```json
[{"order_index": 0, "content": "...", "content_format": "markdown", "explanation": "..."}]
```
Per-option explanation is per-language (lives here, not on `question_options`).

**`questions` (altered):**

- Drop: `stem`, `stem_format`, `language`
- Add: `available_languages` ARRAY(String(5)), nullable, indexed (GIN). Maintained by the service on every translation create/update/delete.
- Keep: `question_type`, `difficulty`, `status`, `source`, `license_status`, `import_job_id`, `version`, `prompt_items`, plus mixins.

**`question_options` (altered):** drop `content`, `content_format`, `explanation`. Keep `question_id`, `order_index`, `is_correct` — the canonical, language-independent answer key used for judging. (One row per option; content is per-language in `question_translations.options`.)

**`explanations` (dropped):** content folded into `question_translations`.

**`users` (altered):** add `language_mode` String(16) NOT NULL DEFAULT `'en'`.

**`question_external_keys` (altered):** unique constraint becomes `(dataset_slug, external_id)` (drop `language` column from the key) — one external key per logical question, because ETL now writes one Question + N translations.

**Sessions:** `language_mode` stored in the existing `practice_sessions.config` and `exam_sessions.config` JSONB columns — no DDL. Snapshots (`practice_answers`/`exam_answers` JSONB) carry both languages + the mode — no DDL.

No new native enums are required (language codes are stored as `String(5)` / `String(16)`, consistent with the existing `Question.language` which was `String(5)`). A module-level `LanguageMode = Literal["en","zh","bilingual"]` and `LanguageCode = Literal["en","zh"]` are defined in `app/models/enums.py` (or a constants module) for type-checking and reused in schemas; they are *not* created as PG enums.

### Snapshot (FR-LANG-07)

`app/services/snapshot.py::snapshot_question(question, translations, options)` captures **all translations** plus the canonical option correctness and the delivered mode:

```json
{
  "question_id": "...",
  "question_type": "single_choice",
  "difficulty": 2,
  "version": 3,
  "available_languages": ["en","zh"],
  "language_mode": "bilingual",
  "options": [{"order_index": 0, "is_correct": true}, ...],
  "translations": {
    "en": {"stem": "...", "stem_format": "markdown",
           "options": [{"order_index":0,"content":"...","content_format":"markdown","explanation":"..."}],
           "correct_answer_rationale": "...", "key_point_summary": "...", "further_reading": "..."},
    "zh": { ... }
  }
}
```

Judging continues to read `is_correct` from the canonical `question_options` (frozen into the snapshot's `options`). Review/feedback render stems/options/explanations from the snapshot, so history is insulated from later edits — unchanged principle, now bilingual. The snapshot is the single source for review, summaries, and reports (rationale is *no longer* read live — it was before; this change makes history fully frozen, a strict improvement for FR-LANG-07).

### Delivery & candidate filtering (FR-LANG-04, 05, 06)

Delivery endpoints (`GET /api/practice/sessions/{id}/questions/{pos}`, `GET /api/exam/sessions/{id}/questions/{pos}`, `GET /api/exam/sessions/{id}/next`) return **both languages** so the client can render by mode and toggle instantly:

```json
{
  "session_id": "...", "position": 1, "total": 20, "question_id": "...",
  "question_type": "single_choice",
  "available_languages": ["en","zh"],
  "language_mode": "bilingual",
  "stem": {"en": "...", "zh": "..."},
  "options": [{"order_index": 0, "content": {"en":"...","zh":"..."}, "content_format": {"en":"markdown","zh":"markdown"}}],
  "elapsed_ms": 0, "time_remaining_ms": 10400000, "previous_answer": null
}
```

Because both languages are in every payload, the client toggles mode with zero round-trips — FR-LANG-06 holds for practice, fixed exam, *and* CAT (the current item's both-language content is already delivered; CAT's forward-only `/next` flow is untouched; toggling does not advance position).

Candidate filters add a language predicate based on the session mode (resolved from session `config["language_mode"]`, defaulting to the user's `language_mode`):
- `en` → `Question.available_languages` contains `'en'`
- `zh` → contains `'zh'`
- `bilingual` → contains both `'en'` and `'zh'`

Applied in: `app/services/practice.py::_candidate_question_ids`, `app/services/exam.py::_assemble`/`_domain_question_ids`, and `app/services/exam.py::_cat_candidate_pool` (CAT pool dicts need no new field — filtering happens at pool construction, before the engine sees candidates, exactly as today).

Answer feedback (practice `AnswerResultOut`) and exam review (`ReviewItemOut`) return explanations in both languages: `correct_rationale: {en,zh}`, `key_point_summary: {en,zh}`, `per_option: [{order_index, is_correct, explanation: {en,zh}}]`.

### User preferences & session API (FR-LANG-03)

- `GET /api/users/me/preferences` → `{language_mode}`
- `PUT /api/users/me/preferences` ← `{language_mode}` (validated `en|zh|bilingual`), gated by `practice:read`
- `language_mode` added to `UserOut` (returned by `/api/auth/me`, `/login`, `/register`) so the frontend has the default without an extra call
- `SessionCreateIn` and `ExamCreateIn` gain optional `language_mode`; if absent → the creating user's default. Stored in `session.config["language_mode"]`.

### Import & ETL (FR-LANG-08)

The import path that actually exists in the codebase is the **ETL dataset pipeline** (`/api/etl/*` preview/commit/rollback, reading `docs/questions/<dataset>/questions.jsonl` which already carries `{en,zh}` bilingual records). There is no separate CSV/XLSX-upload service today; the PRD §10.1 CSV template is the *documented* field interface and maps directly onto the ETL raw-record fields (`question_text`↔`stem.en`, `question_text_zh`↔`stem.zh`, `option_a`↔options[0].text.en, `option_a_zh`↔options[0].text.zh, `explanation`↔explanation.en, `explanation_zh`↔explanation.zh, `option_explanations`/`option_explanations_zh`↔per-option explanation en/zh).

**ETL** (`app/etl/`) — refactored to the one-question-N-translations model:
- `app/etl/extract.py`: unchanged (still parses `{en,zh}` raw records).
- `app/etl/transform.py`: `transform(raw, pending_translation_ids)` produces **one** `CleanedQuestion` carrying bilingual fields (`stem: Bilingual`, `options: [{key, text: Bilingual, explanation: Bilingual}]`, `explanation: Bilingual`) rather than being called once per language. Missing zh for a field is tracked; if *any* zh content is present the question gets a zh translation row (with missing pieces empty + a `needs_revision` flag), else `available_languages=['en']`.
- `app/etl/runner.py`: `_build_cleaned` no longer fans out per language — one `CleanedQuestion` per raw record.
- `app/etl/load.py`: `_apply_one` writes one `Question` per `external_id` plus en (and zh if available) `QuestionTranslation` rows; `QuestionExternalKey` keyed on `(dataset_slug, external_id)` only. Idempotent on external_id; updates bump `version` and write a pre-edit `QuestionRevision`. Validation mirrors PRD §10.2: if any `*_zh` provided, all provided options' zh must be complete and 1:1 with en by letter; incomplete zh flags the question `needs_revision` but does not block the batch (single-question error isolation unchanged).
- `EtlDataset.languages` still records which languages the dataset *offers*; it drives whether a zh translation is written (omit zh entirely when the dataset declares `en`-only).

> Note: PRD v1.1 working-tree edit removes the FR-ETL spec *prose*, but the ETL **code stays** (adapted to the new model) so `/import` and osg10 loading keep working and the system stays runnable. This is consistent with the project memory note that the PRD working-tree edit should not be treated as a code-removal mandate.

### Admin / editor (FR-LANG-09, 10)

- **Question editor** (`app/services/question.py` create/update): accepts translations keyed by language. Publish-time validation (review `approve` transition) requires ≥1 complete language; if both en and zh present, both must be complete (stem + all options + rationale non-empty). `available_languages` recomputed and written on every translation change.
- **Question list**: returns `available_languages` badges; supports filter `missing_language ∈ {en, zh}` (FR-LANG-10).
- **Admin coverage**: `GET /api/admin/questions/language-coverage` → `{en_only, zh_only, both, neither, total}`, gated by `admin:view_reports`. (FR-LANG-10, P2.)

### API surface additions/changes (§9.5)

```
GET    /api/users/me/preferences
PUT    /api/users/me/preferences

# Existing delivery endpoints now return bilingual payloads (see above):
GET    /api/practice/sessions/{id}/questions/{pos}
GET    /api/exam/sessions/{id}/questions/{pos}
GET    /api/exam/sessions/{id}/next

# Existing create endpoints accept optional language_mode:
POST   /api/practice/sessions        # + language_mode
POST   /api/exam/sessions            # + language_mode (fixed + cat)

# Existing question endpoints: bilingual authoring + coverage
POST   /api/questions                # translations: {en?, zh?}
PUT    /api/questions/{id}
GET    /api/questions?missing_language=zh
GET    /api/admin/questions/language-coverage
```

## Migration

One Alembic revision (`backend/app/alembic/versions/<rev>_question_translations.py`), autogenerate-drift-free, tested against `cissp_migtest` (upgrade + downgrade + no-drift test in `tests/test_migrations.py`).

Steps (raw SQL where ORM autogen is insufficient):

1. `CREATE TABLE question_translations (...)` with the unique constraint.
2. Backfill from existing data: for every existing `Question` row, insert one `question_translations` row in its `language` (`'en'` default) built from its `stem`/`stem_format`/`Explanation` fields, and an `options` JSONB array built from its `QuestionOption` rows (`{order_index, content, content_format, explanation}`).
3. **Merge ETL en/zh pairs:** for each `(dataset_slug, external_id)` group having two `Question` rows (one en, one zh via `QuestionExternalKey`):
   - Choose the primary (the `en` row, else the older row). Attach the secondary's content as a second `question_translations` row on the primary (language = secondary's `language`).
   - Repoint child rows from secondary → primary: `practice_answers.question_id`, `exam_answers.question_id`, `user_question_states.question_id` (dedup `uq_user_question_state(user_id, question_id)` conflicts by keeping the row with the later `updated_at`, dropping the other), `question_feedback.question_id`, `question_mappings.question_id`, `question_revisions.question_id`.
   - Delete the secondary's `question_options`, `explanations`, `question_external_keys` rows; soft-delete the secondary `Question`.
4. Set `questions.available_languages` from the set of languages now attached to each question.
5. Alter `questions`: drop `stem`, `stem_format`, `language`; add `available_languages` ARRAY(String(5)) (GIN index).
6. Alter `question_options`: drop `content`, `content_format`, `explanation`.
7. Alter `users`: add `language_mode` String(16) NOT NULL DEFAULT `'en'`.
8. Alter `question_external_keys`: drop the old unique constraint `uq_qek_dataset_ext_lang`, drop the `language` column (or keep nullable, no longer part of the key), add `uq_qek_dataset_ext(dataset_slug, external_id)`.
9. Drop table `explanations`.

`downgrade()` reverses all steps (recreates `explanations`, restores dropped columns, un-merges are not reversible for paired rows — downgrade documents this and recreates the single-language columns populated from the `en` translation, leaving merged zh content in `question_translations` which is dropped). The drift test excludes throwaway `_test_*` tables and the hand-written email index as before.

## Frontend

- **Types** (`src/lib/api/types.ts`): `stem`, option `content`, and explanation text fields become `{en: string; zh: string}` (or `{en: string; zh: string | null}`); add `LanguageMode = "en"|"zh"|"bilingual"`, `LanguageCode = "en"|"zh"`, `available_languages: LanguageCode[]` on question types; `language_mode` on `AuthUser`, `SessionCreateInput`, `ExamCreateInput`.
- **Auth/preferences**: `AuthUser` carries `language_mode`; new `usePreferences` hook (`GET/PUT /api/users/me/preferences`); sidebar gets a language-mode control that sets the default.
- **Session creation**: practice create form (`create-session-form.tsx`, `subset-launcher.tsx`) and exam start form (`start-form.tsx`) gain a language-mode `<Select>` defaulting to the user's pref; payload includes `language_mode`.
- **Runners** (practice `runner.tsx`, fixed `fixed-runner.tsx`, CAT `cat-runner.tsx`): render stem/options/explanation by mode via a new `<BilingualText en zh mode />` helper and a mode toggle (`en` / `zh` / `bilingual`) stored in local state; the toggle re-renders instantly from the already-delivered bilingual payload — selections, timer, and progress are untouched (selections are index-based, language-independent).
- **Options** (`option-list.tsx`, shared): render `content` per mode — `bilingual` shows en and zh side-by-side, 1:1 by `order_index`. Correct/incorrect coloring unchanged (driven by `correct_indexes`).
- **Question editor** (`editor.tsx`): English / Chinese tabs for stem, each option, and explanation; client-side completeness validation mirroring backend publish rules.
- **Summary/report/review** (`summary.tsx`, `report.tsx`, `review.tsx`): render stems/options/rationale by the session mode (snapshots carry both languages).
- **Question list** (`list.tsx`): `available_languages` badges; optional "missing zh"/"missing en" filter.
- **Import** (`import-wizard.tsx`): unchanged surface (still dataset-driven); preview summary continues to show `by_language`.

No new runtime dependencies. Charts remain hand-rolled.

## Testing (TDD)

Backend (pytest, real PG via `cissp_test`):
- Migration: upgrade/downgrade/drift against `cissp_migtest`; a dedicated test that loads two en/zh rows for one `external_id`, runs upgrade, and asserts they merged into one Question with two translations and repointed children.
- `snapshot_question`: freezes both languages + mode; judging unaffected by later edits.
- `question` service: translation CRUD; `available_languages` maintenance; publish validation (≥1 complete; both-complete if both present); list `missing_language` filter.
- `practice` service: candidate filtering per mode (en/zh/bilingual); bilingual delivery payload; session `config["language_mode"]` default from user; answer snapshot carries both + mode; finish summary stems by mode.
- `exam` service: fixed + CAT candidate filtering per mode; bilingual `/next` and `/questions/{pos}` payloads; CAT pool excludes missing-language questions; report/review bilingual rationale.
- `import`/ETL path: one Question + en/zh translations when `*_zh` present; `available_languages` inferred; §10.2 validation (incomplete zh flagged).
- `etl` (`extract/transform/load/runner`): one `CleanedQuestion` per raw; one Question + en+zh translations per `external_id`; idempotent re-run; missing-zh → `available_languages=['en']` + `needs_revision`.
- `auth`/preferences: `GET/PUT /api/users/me/preferences`; `language_mode` in `UserOut`/`/me`/`/login`/`/register`.
- `admin`: `/api/admin/questions/language-coverage` counts.
- Update the existing 366 tests to the new schema (types, fixtures, serializers).

Frontend (Vitest):
- `BilingualText` rendering per mode (en-only / zh-only / side-by-side).
- Mode-toggle state machine (preserves selections/timer/progress).
- Editor completeness validation (mirrors backend rules).
- Practice/exam payload builders include `language_mode`.
- Preferences hook.

## Risks & mitigations

- **Large migration with FK repointing** — mitigated by writing it as tested raw SQL, running it against `cissp_migtest` with merge scenarios, and updating the full suite via TDD before claiming done.
- **Existing tests break en masse** — expected; the test update is part of the plan, done module-by-module with the suite green at each milestone.
- **CAT toggle correctness** — both languages delivered up front, so toggling never calls `/next` and never advances; verified by a CAT-mode-toggle test.
- **Snapshot shape change** — old snapshots (pre-migration) lack `translations`; review code falls back gracefully (`question_snapshot.get("translations")` empty → render from legacy `stem`/`options` keys for historical answers). Documented in the snapshot module.

## Acceptance (PRD §14 + FR-LANG)

1. Questions store en and zh content separately (stem, each option, explanation) — FR-LANG-01.
2. User can select `en`/`zh`/`bilingual`; default saved as a preference; overridable per session — FR-LANG-02/03.
3. `en`/`zh` sessions never deliver missing-language questions — FR-LANG-04.
4. `bilingual` shows both languages side-by-side, options 1:1 — FR-LANG-05.
5. In-runner toggle switches instantly without losing answers/timing/progress — FR-LANG-06.
6. Answer snapshots freeze the mode + both-language content; history unaffected by later edits — FR-LANG-07.
7. Import accepts `*_zh`; single-language questions can be supplemented later — FR-LANG-08.
8. Editor edits/previews en and zh separately; publish validates completeness — FR-LANG-09.
9. Admin can query coverage and filter by missing language — FR-LANG-10.
10. Full stack runs (`docker compose up -d --build`); import → publish → practice (each mode) → fixed exam → CAT all succeed; backend tests green; frontend tests green.
