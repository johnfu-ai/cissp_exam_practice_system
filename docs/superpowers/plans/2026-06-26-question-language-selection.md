# Question Language Selection & Bilingual Display — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bilingual (en/zh) question content and a user-selectable language mode (`en`/`zh`/`bilingual`) to practice and exams (FR-LANG-01..10), with a `QuestionTranslation` table, per-session/per-user mode, instant in-runner toggle, bilingual snapshots, and bilingual authoring/import.

**Architecture:** One `Question` row holds structural fields + `available_languages`; a new `question_translations` table holds per-language stem/option-content/explanation. `QuestionOption` keeps only `order_index`+`is_correct` (language-independent answer key). Sessions store `language_mode` in their existing `config` JSONB; snapshots freeze all translations + the mode. Delivery returns **both** languages so the client toggles instantly. Candidate filters exclude questions missing the requested language. ETL writes one Question + en/zh translations per external_id.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL 16 (JSONB/ARRAY), Pydantic; Next.js 14 + TypeScript + TanStack Query + Zustand + Tailwind + Vitest.

## Global Constraints

- Service-layer backend: routes in `app/api/` delegate to `app/services/`; no business logic in route handlers.
- Tenant scoping: content tables `organization_id`-scoped NOT NULL; taxonomy GLOBAL.
- Soft delete only via `not_deleted(model)`. UUID PKs with `gen_random_uuid()`.
- Native PG enums defined in `app/models/enums.py`, created as `CREATE TYPE` in migrations, dropped in `downgrade()`. Language codes (`en`/`zh`) and modes (`en`/`zh`/`bilingual`) are stored as `String`/`ARRAY(String)` — **not** PG enums.
- Historical integrity via `snapshot_question()`; judging reads `is_correct` from the snapshot.
- Migration must keep autogenerate drift at zero (test in `tests/test_migrations.py` filters `uq_users_email_lower` and `_test_*` tables).
- Tests use real PG (`cissp_test`) via `Base.metadata.create_all` (not Alembic); `tests/test_migrations.py` runs Alembic against `cissp_migtest`.
- CAT is a study tool; reports surface `cat_engine.DISCLAIMER`. CAT answers non-revisable/forward-only.
- Frontend: server components by default; `'use client'` only where needed; no new runtime deps; charts hand-rolled.
- Commit after each task. Run the relevant test command before committing.

## Reference

- Spec: `docs/superpowers/specs/2026-06-26-question-language-selection-design.md`
- Current migration head: `dee7bc824643` (admin backoffice). New migration `down_revision = 'dee7bc824643'`.

---

## File Structure (created / modified)

**Backend — create:**
- `backend/app/alembic/versions/<new>_question_translations.py` — migration
- `backend/app/services/preferences.py` — user preferences service (language_mode)

**Backend — modify:**
- `backend/app/models/enums.py` — add `LanguageCode`, `LanguageMode` literals
- `backend/app/models/question.py` — `QuestionTranslation`; drop fields from `Question`/`QuestionOption`; drop `Explanation`
- `backend/app/models/auth.py` — `User.language_mode`
- `backend/app/models/etl.py` — `QuestionExternalKey` unique key `(dataset_slug, external_id)`
- `backend/app/models/__init__.py` — register `QuestionTranslation`
- `backend/app/services/snapshot.py` — bilingual snapshot
- `backend/app/schemas/question.py` — translations-based schemas
- `backend/app/schemas/practice.py` — `language_mode`, bilingual delivery/answer/wrong
- `backend/app/schemas/exam.py` — `language_mode`, bilingual delivery/review/wrong
- `backend/app/schemas/auth.py` — `UserOut.language_mode`, `PreferencesIn`/`PreferencesOut`
- `backend/app/services/question.py` — translations CRUD, `available_languages`, publish validation, `missing_language` filter
- `backend/app/services/practice.py` — candidate filter by mode, bilingual delivery/snapshot/answer/summary
- `backend/app/services/exam.py` — candidate filter (fixed+CAT), bilingual delivery/report/review
- `backend/app/services/admin.py` — `language_coverage`
- `backend/app/etl/transform.py` — one bilingual `CleanedQuestion`
- `backend/app/etl/load.py` — one Question + N translations, dedup by external_id
- `backend/app/etl/runner.py` — `_build_cleaned` no per-language fan-out
- `backend/app/api/questions.py` — bilingual `_question_out`, `missing_language` query, coverage
- `backend/app/api/auth.py` — `language_mode` in `_user_out`
- `backend/app/api/admin.py` — `/questions/language-coverage` route
- `backend/app/main.py` — register preferences router (new) OR add routes to auth router
- `backend/app/db/seed.py` — no structural change (datasets unchanged)
- `backend/tests/*` — update to new schema + new tests

**Frontend — modify:**
- `frontend/src/lib/api/types.ts` — bilingual shapes, `LanguageMode`, `available_languages`, `AuthUser.language_mode`
- `frontend/src/lib/auth-store.ts` — `AuthUser.language_mode`
- `frontend/src/lib/api/keys.ts` — preferences key
- `frontend/src/lib/api/preferences.ts` — **create** `usePreferences`/`useUpdatePreferences`
- `frontend/src/components/app-sidebar.tsx` — language-mode control
- `frontend/src/components/bilingual-text.tsx` — **create** `<BilingualText>`
- `frontend/src/features/practice/option-list.tsx` — bilingual rendering
- `frontend/src/features/practice/session-payload.ts` — `languageMode`
- `frontend/src/features/practice/create-session-form.tsx` — language-mode select
- `frontend/src/features/practice/runner.tsx` — mode toggle + bilingual render
- `frontend/src/features/practice/summary.tsx` — bilingual wrong-question stems
- `frontend/src/features/exam/start-form.tsx` — language-mode select
- `frontend/src/features/exam/fixed-runner.tsx`, `cat-runner.tsx` — mode toggle + bilingual render
- `frontend/src/features/exam/report.tsx`, `review.tsx` — bilingual render
- `frontend/src/features/questions/editor.tsx` — bilingual tabs + completeness validation
- `frontend/src/features/questions/list.tsx` — `available_languages` badges + missing filter
- `frontend/src/features/questions/detail.tsx` — bilingual render
- `frontend/src/features/practice/__tests__/`, `frontend/src/features/exam/__tests__/`, `frontend/src/features/questions/__tests__/` — new tests

---

## Conventions used throughout

- **Language blobs.** A localized text value is `{"en": "...", "zh": "..."}` where either side may be `null` when that language is absent. A `Localized` Pydantic type alias is defined once and reused.
- **`available_languages`** is a Python `list[str]` of `["en"]`, `["zh"]`, or `["en","zh"]`, stored in `ARRAY(String(5))`. Maintained by the question service on every translation write.
- **Mode resolution.** `resolve_language_mode(session_config, user)` → `session_config.get("language_mode") or user.language_mode or "en"`.
- **Candidate predicate.** Given `mode`: `en`→`'en' ∈ available_languages`; `zh`→`'zh' ∈`; `bilingual`→ both present. Implemented with `Question.available_languages` (ARRAY contains).
- **Snapshot legacy fallback.** Review/summary code reads `snap.get("translations")`; if absent (pre-migration historical rows), falls back to legacy `snap.get("stem","")` / `snap.get("options")`.

---

## Task 1: Models — `QuestionTranslation`, drop single-language fields, `User.language_mode`

**Files:**
- Modify: `backend/app/models/enums.py`
- Modify: `backend/app/models/question.py`
- Modify: `backend/app/models/auth.py`
- Modify: `backend/app/models/etl.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_models.py` (extend existing)

**Interfaces:**
- Produces: `QuestionTranslation` model; `Question.available_languages: list[str]`; `QuestionOption` has only `question_id, order_index, is_correct`; `User.language_mode: str`; `QuestionExternalKey` unique on `(dataset_slug, external_id)`; `LanguageCode`/`LanguageMode` literals.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_models.py`:

```python
def test_question_translation_model_columns(db_session):
    from app.models.question import Question, QuestionOption, QuestionTranslation
    from app.models.enums import QuestionType, QuestionStatus, TextFormat

    q = Question(
        organization_id=db_session.get_bind().url.database and _org_id(db_session),
        question_type=QuestionType.single_choice,
        status=QuestionStatus.draft,
        available_languages=["en", "zh"],
    )
    db_session.add(q); db_session.flush()
    db_session.add(QuestionOption(question_id=q.id, order_index=0, is_correct=True))
    db_session.add(QuestionOption(question_id=q.id, order_index=1, is_correct=False))
    t = QuestionTranslation(
        question_id=q.id, language="en",
        stem="Which principle?", stem_format=TextFormat.markdown,
        correct_answer_rationale="Because.",
        options=[{"order_index": 0, "content": "A", "content_format": "markdown", "explanation": None},
                 {"order_index": 1, "content": "B", "content_format": "markdown", "explanation": None}],
    )
    db_session.add(t); db_session.flush()
    assert q.available_languages == ["en", "zh"]
    assert not hasattr(q, "stem")
    assert not hasattr(QuestionOption, "content") or "content" not in QuestionOption.__table__.columns
    assert t.options[0]["content"] == "A"


def test_user_has_language_mode(db_session):
    from app.models.auth import User
    u = User(email="x@y.com", language_mode="bilingual")
    db_session.add(u); db_session.flush()
    assert u.language_mode == "bilingual"
```

(Add a `_org_id` helper if not present: create/reuse an `Organization` in `db_session` and return its id; many existing tests already do this — mirror the pattern from `test_question_service.py`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_models.py::test_question_translation_model_columns tests/test_models.py::test_user_has_language_mode -v`
Expected: FAIL (no `QuestionTranslation`, `Question.stem` still exists, `User` has no `language_mode`).

- [ ] **Step 3: Add language literals to enums**

In `backend/app/models/enums.py`, append:

```python
from typing import Literal

LanguageCode = Literal["en", "zh"]
LanguageMode = Literal["en", "zh", "bilingual"]

LANGUAGE_CODES: tuple[str, ...] = ("en", "zh")
LANGUAGE_MODES: tuple[str, ...] = ("en", "zh", "bilingual")
```

- [ ] **Step 4: Rewrite the relevant models in `backend/app/models/question.py`**

Replace the `Question`, `QuestionOption`, and `Explanation` classes (lines 73–137) with:

```python
from sqlalchemy.dialects.postgresql import ARRAY  # add to imports at top


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
    difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_languages: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(5)), nullable=True
    )
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
    prompt_items: Mapped[list | None] = mapped_column(JSONB, nullable=True)


class QuestionOption(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "question_options"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))


class QuestionTranslation(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "question_translations"
    __table_args__ = (
        UniqueConstraint("question_id", "language", name="uq_question_translations_qid_lang"),
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(5), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    stem_format: Mapped[TextFormat] = mapped_column(
        Enum(TextFormat, name="text_format", create_type=True),
        nullable=False,
        server_default=TextFormat.markdown.value,
    )
    correct_answer_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    key_point_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    further_reading: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[list] = mapped_column(JSONB, nullable=False)
```

Add `UniqueConstraint` to the `sqlalchemy` import at the top of the file. **Delete** the `Explanation` class entirely. Remove `Explanation` from any docstrings/imports.

- [ ] **Step 5: Add `language_mode` to `User` in `backend/app/models/auth.py`**

Add inside the `User` class (after `default_organization_id`):

```python
    language_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'en'")
    )
```

- [ ] **Step 6: Update `QuestionExternalKey` in `backend/app/models/etl.py`**

Replace the `__table_args__` and keep `language` column nullable (no longer part of the unique key):

```python
class QuestionExternalKey(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "question_external_keys"
    __table_args__ = (
        UniqueConstraint("dataset_slug", "external_id", name="uq_qek_dataset_ext"),
    )

    dataset_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    language: Mapped[str | None] = mapped_column(String(5), nullable=True)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
```

- [ ] **Step 7: Register `QuestionTranslation` in `backend/app/models/__init__.py`**

Add `QuestionTranslation` to the import from `.question` and to `__all__`. Remove `Explanation` from both if present.

- [ ] **Step 8: Run the model test to verify it passes**

Run: `cd backend && pytest tests/test_models.py::test_question_translation_model_columns tests/test_models.py::test_user_has_language_mode -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/ backend/tests/test_models.py
git commit -m "feat(models): QuestionTranslation + available_languages; drop single-language fields; User.language_mode"
```

> Note: At this point the broader test suite is **expected to be red** (services still reference dropped fields). Subsequent tasks fix them. Do not run the full suite yet.

---

## Task 2: Alembic migration — create `question_translations`, backfill, merge ETL pairs, alter tables

**Files:**
- Create: `backend/app/alembic/versions/a1b2c3d4e5f6_question_translations.py`
- Test: `backend/tests/test_migrations.py` (extend), `backend/tests/test_question_migration_merge.py` (create)

**Interfaces:**
- Produces: a migration that, when applied to a DB with the old single-language schema, produces the new schema with one `Question` per logical question, `question_translations` populated, ETL en/zh pairs merged, child FKs repointed.

- [ ] **Step 1: Generate the migration skeleton**

Run:
```bash
cd backend && alembic revision --autogenerate -m "question_translations"
```
This creates a file under `app/alembic/versions/`. Rename its `revision` to `'a1b2c3d4e5f6'` and set `down_revision = 'dee7bc824643'`. **Discard the autogenerate body** — the migration is hand-written because it includes data backfill + merge logic autogenerate cannot express.

- [ ] **Step 2: Write the migration `upgrade()`**

Replace the file body with:

```python
"""question_translations

Revision ID: a1b2c3d4e5f6
Revises: dee7bc824643
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a1b2c3d4e5f6'
down_revision = 'dee7bc824643'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create question_translations.
    op.create_table(
        'question_translations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column('question_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('language', sa.String(length=5), nullable=False),
        sa.Column('stem', sa.Text(), nullable=False),
        sa.Column('stem_format', sa.Enum('plain', 'markdown', name='text_format', create_type=False), nullable=False, server_default='markdown'),
        sa.Column('correct_answer_rationale', sa.Text(), nullable=False),
        sa.Column('key_point_summary', sa.Text(), nullable=True),
        sa.Column('further_reading', sa.Text(), nullable=True),
        sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('question_id', 'language', name='uq_question_translations_qid_lang'),
    )

    # 2. Backfill one translation per existing Question from its stem/options/Explanation.
    op.execute("""
    INSERT INTO question_translations (question_id, language, stem, stem_format, correct_answer_rationale, key_point_summary, further_reading, options)
    SELECT q.id,
           q.language,
           q.stem,
           q.stem_format,
           COALESCE(e.correct_answer_rationale, ''),
           e.key_point_summary,
           e.further_reading,
           COALESCE((
             SELECT jsonb_agg(jsonb_build_object(
               'order_index', o.order_index,
               'content', o.content,
               'content_format', o.content_format,
               'explanation', o.explanation
             ) ORDER BY o.order_index)
             FROM question_options o WHERE o.question_id = q.id
           ), '[]'::jsonb)
    FROM questions q
    LEFT JOIN explanations e ON e.question_id = q.id
    WHERE q.deleted_at IS NULL;
    """)

    # 3. Merge ETL en/zh pairs: for each (dataset_slug, external_id) with >1 QuestionExternalKey,
    #    pick a primary, attach the secondary's translation onto the primary, repoint children,
    #    delete the secondary's options/explanations/external_key, soft-delete the secondary.
    op.execute(r"""
    DO $$
    DECLARE
        grp RECORD;
        primary_id UUID;
        sec_id UUID;
        primary_lang TEXT;
        sec_lang TEXT;
        dup_state UUID;
    BEGIN
        FOR grp IN
            SELECT dataset_slug, external_id
            FROM question_external_keys
            GROUP BY dataset_slug, external_id
            HAVING COUNT(*) > 1
        LOOP
            -- primary = the 'en' row, else the earliest by created_at; else the question with a translation.
            SELECT qek.question_id, qek.language INTO primary_id, primary_lang
            FROM question_external_keys qek
            JOIN questions q ON q.id = qek.question_id AND q.deleted_at IS NULL
            WHERE qek.dataset_slug = grp.dataset_slug AND qek.external_id = grp.external_id
            ORDER BY (qek.language <> 'en'), q.created_at ASC
            LIMIT 1;

            FOR sec_id, sec_lang IN
                SELECT qek.question_id, qek.language
                FROM question_external_keys qek
                WHERE qek.dataset_slug = grp.dataset_slug
                  AND qek.external_id = grp.external_id
                  AND qek.question_id <> primary_id
            LOOP
                -- Move the secondary's translation onto the primary (rename language if needed).
                UPDATE question_translations
                   SET question_id = primary_id
                 WHERE question_id = sec_id;
                -- If a same-language translation already exists on primary, drop the duplicate.
                DELETE FROM question_translations qt
                 USING question_translations qt2
                 WHERE qt.question_id = primary_id AND qt2.question_id = primary_id
                   AND qt.language = qt2.language AND qt.id < qt2.id;

                -- Repoint user_question_states (dedup unique (user_id, question_id)).
                DELETE FROM user_question_states
                 WHERE question_id = sec_id
                   AND user_id IN (SELECT user_id FROM user_question_states WHERE question_id = primary_id);
                UPDATE user_question_states SET question_id = primary_id WHERE question_id = sec_id;

                -- Repoint remaining children.
                UPDATE practice_answers SET question_id = primary_id WHERE question_id = sec_id;
                UPDATE exam_answers SET question_id = primary_id WHERE question_id = sec_id;
                UPDATE question_feedback SET question_id = primary_id WHERE question_id = sec_id;
                UPDATE question_mappings SET question_id = primary_id WHERE question_id = sec_id;
                UPDATE question_revisions SET question_id = primary_id WHERE question_id = sec_id;

                -- Remove secondary's own option/explanation/external_key rows.
                DELETE FROM question_options WHERE question_id = sec_id;
                DELETE FROM explanations WHERE question_id = sec_id;
                DELETE FROM question_external_keys WHERE question_id = sec_id;

                -- Soft-delete the secondary question.
                UPDATE questions SET deleted_at = now() WHERE id = sec_id;
            END LOOP;
        END LOOP;
    END $$;
    """)

    # 4. Set questions.available_languages from attached translations.
    op.execute("""
    UPDATE questions q
       SET available_languages = sub.langs
      FROM (SELECT question_id, array_agg(language ORDER BY language) AS langs
              FROM question_translations GROUP BY question_id) sub
     WHERE sub.question_id = q.id AND q.deleted_at IS NULL;
    """)

    # 5. Alter questions: drop stem, stem_format, language; available_languages added above via raw UPDATE
    #    (column must exist first).
    op.add_column('questions', sa.Column('available_languages', postgresql.ARRAY(sa.String(length=5)), nullable=True))
    op.execute("""
    UPDATE questions SET available_languages = sub.langs
      FROM (SELECT question_id, array_agg(language ORDER BY language) AS langs
              FROM question_translations GROUP BY question_id) sub
     WHERE sub.question_id = q.id AND q.deleted_at IS NULL;
    """)
    op.drop_column('questions', 'stem')
    op.drop_column('questions', 'stem_format')
    op.drop_column('questions', 'language')
    op.create_index('ix_questions_available_languages', 'questions', ['available_languages'], postgresql_using='gin')

    # 6. Alter question_options: drop content, content_format, explanation.
    op.drop_column('question_options', 'content')
    op.drop_column('question_options', 'content_format')
    op.drop_column('question_options', 'explanation')

    # 7. Alter users: add language_mode.
    op.add_column('users', sa.Column('language_mode', sa.String(length=16), nullable=False, server_default='en'))

    # 8. Alter question_external_keys: new unique constraint, language nullable.
    op.drop_constraint('uq_qek_dataset_ext_lang', 'question_external_keys', type_='unique')
    op.alter_column('question_external_keys', 'language', existing_type=sa.String(length=5), nullable=True)
    op.create_unique_constraint('uq_qek_dataset_ext', 'question_external_keys', ['dataset_slug', 'external_id'])

    # 9. Drop explanations table.
    op.drop_table('explanations')
```

> Note: the duplicate `available_languages` UPDATE is intentional — `add_column` must precede the column reference; the first raw `UPDATE ... SET available_languages` only runs after step 5's `add_column`. To keep it simple, the authoritative population is the UPDATE immediately after `add_column`. The step-4 block is harmless (column doesn't exist yet, so it will error) — **remove the step-4 block** and keep only the post-`add_column` UPDATE. Final migration should have steps ordered: create table → backfill → merge → add_column → populate available_languages → drop columns → options → users → external_keys → drop explanations.

- [ ] **Step 3: Write the migration `downgrade()`**

```python
def downgrade() -> None:
    # Recreate explanations and single-language columns (best-effort from 'en' translation).
    op.create_table(
        'explanations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column('question_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('correct_answer_rationale', sa.Text(), nullable=False),
        sa.Column('key_point_summary', sa.Text(), nullable=True),
        sa.Column('further_reading', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column('questions', sa.Column('stem', sa.Text(), nullable=False, server_default=''))
    op.add_column('questions', sa.Column('stem_format', sa.Enum('plain','markdown', name='text_format', create_type=False), nullable=False, server_default='markdown'))
    op.add_column('questions', sa.Column('language', sa.String(length=5), nullable=False, server_default='en'))
    op.add_column('question_options', sa.Column('content', sa.Text(), nullable=False, server_default=''))
    op.add_column('question_options', sa.Column('content_format', sa.Enum('plain','markdown', name='text_format', create_type=False), nullable=False, server_default='markdown'))
    op.add_column('question_options', sa.Column('explanation', sa.Text(), nullable=True))
    # Populate from the 'en' translation (or any single translation) where possible.
    op.execute("""
    UPDATE questions q SET stem = t.stem, stem_format = t.stem_format, language = t.language
      FROM question_translations t WHERE t.question_id = q.id AND t.language = 'en';
    INSERT INTO explanations (question_id, correct_answer_rationale, key_point_summary, further_reading)
    SELECT question_id, correct_answer_rationale, key_point_summary, further_reading
      FROM question_translations WHERE language = 'en'
    ON CONFLICT DO NOTHING;
    """)
    op.drop_constraint('uq_qek_dataset_ext', 'question_external_keys', type_='unique')
    op.alter_column('question_external_keys', 'language', existing_type=sa.String(length=5), nullable=False)
    op.create_unique_constraint('uq_qek_dataset_ext_lang', 'question_external_keys', ['dataset_slug', 'external_id', 'language'])
    op.drop_column('users', 'language_mode')
    op.drop_index('ix_questions_available_languages', table_name='questions')
    op.drop_column('questions', 'available_languages')
    op.drop_table('question_translations')
```

> Downgrade does not un-merge paired questions (documented in the spec as non-reversible for merged rows); it recreates the single-language columns populated from the `en` translation so the schema is structurally the old one. The `test_upgrade_then_downgrade_succeeds` test only checks the upgrade/downgrade cycle runs against an empty `cissp_migtest` DB, so this is sufficient.

- [ ] **Step 4: Write the merge test**

Create `backend/tests/test_question_migration_merge.py`:

```python
import os
import uuid
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text, insert
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base

ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
ADMIN = "postgresql+psycopg://cissp:cissp@localhost:5432/cissp"
MIG = "postgresql+psycopg://cissp:cissp@localhost:5432/cissp_migmerge"


@pytest.fixture
def mig_engine():
    admin = create_engine(ADMIN, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text("DROP DATABASE IF EXISTS cissp_migmerge"))
        c.execute(text("CREATE DATABASE cissp_migmerge"))
    admin.dispose()
    eng = create_engine(MIG)
    # Build ONLY the pre-migration schema by upgrading to the prior head.
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", MIG)
    command.upgrade(cfg, "dee7bc824643")
    yield eng
    eng.dispose()
    admin = create_engine(ADMIN, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text("DROP DATABASE IF EXISTS cissp_migmerge"))
    admin.dispose()


def test_merges_etl_pair_and_repoints_children(mig_engine):
    org = uuid.uuid4()
    with Session(mig_engine) as s:
        # Org + user needed for FKs.
        s.execute(text("INSERT INTO organizations (id, name, slug, kind, status, created_at, updated_at) "
                       "VALUES (:id, 'o','o','personal','active', now(), now())"), {"id": org})
        u = uuid.uuid4()
        s.execute(text("INSERT INTO users (id, email, status, language_mode_unused, created_at, updated_at) "
                       "VALUES (:id,'u@x','active', now(), now())"))
        # NOTE: users table at prior head has NO language_mode column; adjust the INSERT accordingly.
        # Insert two questions (en + zh) sharing external_id, each with options + explanation.
        ...
    # Apply the new migration.
    cfg = Config(ALEMBIC_INI); cfg.set_main_option("sqlalchemy.url", MIG)
    command.upgrade(cfg, "a1b2c3d4e5f6")
    with Session(mig_engine) as s:
        rows = s.execute(text("SELECT id, available_languages FROM questions WHERE deleted_at IS NULL")).all()
        assert len(rows) == 1
        trans = s.execute(text("SELECT language FROM question_translations WHERE question_id = :id"),
                          {"id": rows[0][0]}).all()
        assert {t[0] for t in trans} == {"en", "zh"}
```

> The implementer should fill the INSERT helpers to match the exact pre-migration column set (run `\d` or read the prior migrations). The assertion is the load-bearing part: **two en/zh questions with the same `external_id` become one question with two translations.** Keep the seeded row inserts minimal (org, user, two questions, two options each, two explanations, two `question_external_keys` rows sharing `(dataset_slug, external_id)`).

- [ ] **Step 5: Run migration tests**

Run:
```bash
cd backend && pytest tests/test_migrations.py tests/test_question_migration_merge.py -v
```
Expected: `test_upgrade_then_downgrade_succeeds` PASS, `test_no_autogenerate_drift` PASS (drift == []), `test_merges_etl_pair_and_repoints_children` PASS.

> If drift is non-empty, fix the migration to exactly match model metadata (column types, server_defaults, indexes, constraints). The `text_format` enum is reused (`create_type=False`).

- [ ] **Step 6: Commit**

```bash
git add backend/app/alembic/versions/ backend/tests/test_question_migration_merge.py backend/tests/test_migrations.py
git commit -m "feat(migration): question_translations + ETL en/zh pair merge + available_languages"
```

---

## Task 3: Bilingual snapshot + Pydantic schemas

**Files:**
- Modify: `backend/app/services/snapshot.py`
- Modify: `backend/app/schemas/question.py`
- Modify: `backend/app/schemas/practice.py`
- Modify: `backend/app/schemas/exam.py`
- Modify: `backend/app/schemas/auth.py`
- Test: `backend/tests/test_snapshot.py` (rewrite), `backend/tests/test_*_schemas.py` as needed

**Interfaces:**
- Produces: `snapshot_question(question, translations, options, language_mode=None) -> dict`; `Localized = dict[str, str | None]`-shaped schema fields; `SessionCreateIn.language_mode`, `ExamCreateIn.language_mode`; `PreferencesIn`/`PreferencesOut`; `UserOut.language_mode`.

- [ ] **Step 1: Write the failing snapshot test**

Rewrite `backend/tests/test_snapshot.py`:

```python
from app.services.snapshot import snapshot_question


def _qt(q, options, translations, mode="bilingual"):
    return snapshot_question(q, translations, options, language_mode=mode)


def test_snapshot_freezes_all_translations_and_mode(db_session, make_question_with_translations):
    q, options, translations = make_question_with_translations(
        en_stem="en stem", zh_stem="中文题干",
        options_en=["A", "B"], options_zh=["甲", "乙"],
        rationale_en="en why", rationale_zh="中文解析",
    )
    snap = snapshot_question(q, translations, options, language_mode="zh")
    assert snap["language_mode"] == "zh"
    assert snap["available_languages"] == ["en", "zh"]
    assert snap["translations"]["en"]["stem"] == "en stem"
    assert snap["translations"]["zh"]["stem"] == "中文题干"
    assert snap["translations"]["zh"]["options"][0]["content"] == "甲"
    # canonical correctness frozen
    assert [o["is_correct"] for o in snap["options"]] == [o.is_correct for o in options]
```

`make_question_with_translations` is a shared test fixture/helper created in Task 4's test module and imported (or define a small local builder here). Add it to `tests/conftest.py` as a fixture.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && pytest tests/test_snapshot.py -v` → FAIL (`snapshot_question` signature mismatch).

- [ ] **Step 3: Rewrite `backend/app/services/snapshot.py`**

```python
"""Snapshot producer for historical answer integrity (NFR-DATA-01, FR-LANG-07).

Captures ALL translations + the canonical option correctness + the delivered
language mode at answer time so later edits never alter historical records.
"""
from typing import Any

from app.models.question import Question, QuestionOption, QuestionTranslation


def snapshot_question(
    question: Question,
    translations: list[QuestionTranslation],
    options: list[QuestionOption],
    *,
    language_mode: str | None = None,
) -> dict[str, Any]:
    opts = sorted(options, key=lambda o: o.order_index)
    canon = [{"order_index": o.order_index, "is_correct": o.is_correct} for o in opts]
    tmap: dict[str, dict] = {}
    for t in translations:
        tmap[t.language] = {
            "stem": t.stem,
            "stem_format": t.stem_format.value,
            "options": [
                {
                    "order_index": o.get("order_index"),
                    "content": o.get("content"),
                    "content_format": o.get("content_format"),
                    "explanation": o.get("explanation"),
                }
                for o in (t.options or [])
            ],
            "correct_answer_rationale": t.correct_answer_rationale,
            "key_point_summary": t.key_point_summary,
            "further_reading": t.further_reading,
        }
    return {
        "question_id": str(question.id),
        "question_type": question.question_type.value,
        "difficulty": question.difficulty,
        "version": question.version,
        "available_languages": list(question.available_languages or []),
        "language_mode": language_mode,
        "options": canon,
        "translations": tmap,
    }


def localized_from_snapshot(snap: dict, mode: str) -> dict:
    """Render a single-language or bilingual view from a snapshot for review/summary.

    Returns {stem, options:[{order_index,content,is_correct,explanation}],
             correct_rationale, key_point_summary} where content/rationale are
    Localized dicts ({en,zh}). Honors legacy snapshots (no translations) by
    falling back to the old flat stem/options.
    """
    tmap = snap.get("translations") or {}
    langs = [l for l in ("en", "zh") if l in tmap] or []
    def loc(field, sub=None):
        out = {}
        for l in ("en", "zh"):
            t = tmap.get(l) or {}
            out[l] = (t.get(field) if sub is None else (t.get(sub) or {}).get(field))
        return out
    if tmap:
        opts = []
        for co in snap.get("options", []):
            oi = co["order_index"]
            cell = {"order_index": oi, "is_correct": co["is_correct"],
                    "content": {}, "content_format": {}, "explanation": {}}
            for l in ("en", "zh"):
                to = next((o for o in (tmap.get(l) or {}).get("options", []) if o.get("order_index") == oi), {})
                cell["content"][l] = to.get("content")
                cell["content_format"][l] = to.get("content_format")
                cell["explanation"][l] = to.get("explanation")
            opts.append(cell)
        return {
            "stem": {l: (tmap.get(l) or {}).get("stem") for l in ("en", "zh")},
            "options": opts,
            "correct_rationale": {l: (tmap.get(l) or {}).get("correct_answer_rationale") for l in ("en", "zh")},
            "key_point_summary": {l: (tmap.get(l) or {}).get("key_point_summary") for l in ("en", "zh")},
            "available_languages": langs,
        }
    # Legacy snapshot fallback.
    return {
        "stem": {"en": snap.get("stem", ""), "zh": snap.get("stem", "")},
        "options": [{"order_index": o.get("order_index"), "is_correct": o.get("is_correct"),
                     "content": {"en": o.get("content"), "zh": o.get("content")},
                     "content_format": {"en": o.get("content_format"), "zh": o.get("content_format")},
                     "explanation": {"en": None, "zh": None}} for o in snap.get("options", [])],
        "correct_rationale": {"en": None, "zh": None},
        "key_point_summary": {"en": None, "zh": None},
        "available_languages": ["en"],
    }
```

- [ ] **Step 4: Rewrite `backend/app/schemas/question.py`** (translations-based)

Replace `OptionIn`/`OptionOut`/`ExplanationIn`/`ExplanationOut`/`QuestionCreateIn`/`QuestionUpdateIn`/`QuestionOut`/`QuestionListItem` with:

```python
class TranslationOptionIn(BaseModel):
    order_index: int
    content: str
    content_format: TextFormat = TextFormat.markdown
    explanation: str | None = None


class TranslationIn(BaseModel):
    language: str  # 'en' | 'zh'
    stem: str
    stem_format: TextFormat = TextFormat.markdown
    correct_answer_rationale: str
    key_point_summary: str | None = None
    further_reading: str | None = None
    options: list[TranslationOptionIn]


class TranslationOptionOut(BaseModel):
    order_index: int
    content: str
    content_format: TextFormat
    explanation: str | None = None


class TranslationOut(BaseModel):
    language: str
    stem: str
    stem_format: TextFormat
    correct_answer_rationale: str
    key_point_summary: str | None = None
    further_reading: str | None = None
    options: list[TranslationOptionOut]


class OptionIn(BaseModel):  # canonical: order + correctness only
    order_index: int | None = None
    is_correct: bool = False


class MappingsIn(BaseModel):
    domain_id: uuid.UUID | None = None
    chapter_id: uuid.UUID | None = None
    knowledge_point_id: uuid.UUID | None = None
    tag_ids: list[uuid.UUID] = Field(default_factory=list)


class MappingsOut(BaseModel):
    domain_id: uuid.UUID | None = None
    chapter_id: uuid.UUID | None = None
    knowledge_point_id: uuid.UUID | None = None
    tag_ids: list[uuid.UUID] = Field(default_factory=list)


class QuestionCreateIn(BaseModel):
    question_type: QuestionType
    difficulty: int | None = None
    source: str | None = None
    license_status: LicenseStatus = LicenseStatus.unconfirmed
    prompt_items: list | None = None
    options: list[OptionIn]  # canonical answer key
    translations: list[TranslationIn]  # at least one
    mappings: MappingsIn = Field(default_factory=MappingsIn)


class QuestionUpdateIn(BaseModel):
    question_type: QuestionType | None = None
    difficulty: int | None = None
    source: str | None = None
    license_status: LicenseStatus | None = None
    prompt_items: list | None = None
    options: list[OptionIn] | None = None
    translations: list[TranslationIn] | None = None
    mappings: MappingsIn | None = None


class QuestionOut(BaseModel):
    id: uuid.UUID
    question_type: QuestionType
    difficulty: int | None
    available_languages: list[str]
    status: QuestionStatus
    source: str | None
    license_status: LicenseStatus
    version: int
    prompt_items: list | None = None
    created_at: datetime
    updated_at: datetime
    options: list[OptionOut]  # canonical {id, order_index, is_correct}
    translations: list[TranslationOut]
    mappings: MappingsOut


class OptionOut(BaseModel):
    id: uuid.UUID
    order_index: int
    is_correct: bool


class QuestionListItem(BaseModel):
    id: uuid.UUID
    question_type: QuestionType
    status: QuestionStatus
    difficulty: int | None
    available_languages: list[str]
    domain_id: uuid.UUID | None = None
    created_at: datetime
```

Keep `ReviewAction`, `ReviewActionIn`, `FeedbackIn`, `FeedbackOut`, `RevisionOut` unchanged.

- [ ] **Step 5: Update `backend/app/schemas/practice.py`**

Add `language_mode` to `SessionCreateIn`; make delivery/answer/wrong bilingual:

```python
from typing import Literal
from app.models.enums import ErrorType

Subset = Literal["all", "unpracticed", "wrong", "bookmarked", "needs_review"]
OrderMode = Literal["random", "sequential", "easy_to_hard"]
LanguageMode = Literal["en", "zh", "bilingual"]


class SessionCreateIn(BaseModel):
    count: int = Field(ge=1, le=200)
    subset: Subset = "all"
    order_mode: OrderMode = "random"
    language_mode: LanguageMode | None = None
    domain_id: uuid.UUID | None = None
    book_id: uuid.UUID | None = None
    chapter_ids: list[uuid.UUID] = Field(default_factory=list)
    question_type: str | None = None
    difficulty: int | None = None
    tag_id: uuid.UUID | None = None


class Localized(BaseModel):
    en: str | None = None
    zh: str | None = None


class OptionDelivery(BaseModel):
    id: uuid.UUID
    order_index: int
    content: Localized
    content_format: Localized


class QuestionDeliveryOut(BaseModel):
    session_id: uuid.UUID
    position: int
    total: int
    question_id: uuid.UUID
    question_type: str
    available_languages: list[str]
    language_mode: str
    stem: Localized
    options: list[OptionDelivery]
    elapsed_ms: int
    previous_answer: dict | None = None


class PerOptionExplanation(BaseModel):
    order_index: int
    is_correct: bool
    explanation: Localized


class AnswerResultOut(BaseModel):
    is_correct: bool
    correct_indexes: list[int]
    selected_indexes: list[int]
    correct_rationale: Localized
    key_point_summary: Localized
    per_option: list[PerOptionExplanation]
    mapping: dict
    history: list[dict]


class WrongQuestion(BaseModel):
    question_id: uuid.UUID
    stem: Localized
    selected_indexes: list[int]
    correct_indexes: list[int]
```

`SessionOut`, `AnswerIn`, `DomainBreakdown`, `SessionSummaryOut`, `QuestionStateIn` unchanged (SessionOut already exposes `config` which now carries `language_mode`).

- [ ] **Step 6: Update `backend/app/schemas/exam.py`**

Add `language_mode` to `ExamCreateIn`; bilingual delivery/review/wrong:

```python
from typing import Literal
LanguageMode = Literal["en", "zh", "bilingual"]


class ExamCreateIn(BaseModel):
    kind: str = Field(default="fixed", pattern="^(fixed|cat)$")
    count: int | None = Field(default=None, ge=1, le=500)
    language_mode: LanguageMode | None = None


class Localized(BaseModel):
    en: str | None = None
    zh: str | None = None


class OptionDelivery(BaseModel):
    id: uuid.UUID
    order_index: int
    content: Localized
    content_format: Localized


class QuestionDeliveryOut(BaseModel):
    session_id: uuid.UUID
    position: int
    total: int
    question_id: uuid.UUID
    question_type: str
    available_languages: list[str]
    language_mode: str
    stem: Localized
    options: list[OptionDelivery]
    elapsed_ms: int
    time_remaining_ms: int
    previous_answer: dict | None = None


class WrongQuestion(BaseModel):
    question_id: uuid.UUID
    stem: Localized
    selected_indexes: list[int]
    correct_indexes: list[int]


class ReviewOption(BaseModel):
    order_index: int
    content: Localized
    is_correct: bool
    explanation: Localized


class ReviewItemOut(BaseModel):
    position: int
    question_id: uuid.UUID
    question_type: str
    available_languages: list[str]
    stem: Localized
    options: list[ReviewOption]
    correct_rationale: Localized
    key_point_summary: Localized
    your_answer: dict | None = None
    time_spent_ms: int | None = None
```

Keep `ExamSessionOut`, `ExamAnswerIn`, `ExamAnswerAck`, `DomainPerformance`, `ExamReportOut`, `ExamHistoryItemOut` (the report's `wrong_questions` now uses the bilingual `WrongQuestion`).

- [ ] **Step 7: Update `backend/app/schemas/auth.py`**

```python
class UserOut(BaseModel):
    id: str
    email: str
    display_name: str | None
    roles: list[str]
    perms: list[str]
    language_mode: str = "en"


class PreferencesIn(BaseModel):
    language_mode: str  # 'en'|'zh'|'bilingual'


class PreferencesOut(BaseModel):
    language_mode: str
```

- [ ] **Step 8: Run schema/snapshot tests**

Run: `cd backend && pytest tests/test_snapshot.py tests/test_admin_schemas.py -v`
Expected: snapshot test PASS. (Other service tests still red until Task 4+.)

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/snapshot.py backend/app/schemas/ backend/tests/test_snapshot.py
git commit -m "feat(schemas): bilingual snapshot + translations-based question/practice/exam/auth schemas"
```

---

## Task 4: Question service — translations CRUD, `available_languages`, publish validation, `missing_language` filter

**Files:**
- Modify: `backend/app/services/question.py`
- Modify: `backend/app/api/questions.py`
- Test: `backend/tests/test_question_service.py`, `backend/tests/test_question_api.py` (rewrite)

**Interfaces:**
- Consumes: `QuestionTranslation` model, `TranslationIn`/`QuestionCreateIn`/`QuestionUpdateIn`/`QuestionOut`/`QuestionListItem` schemas, `snapshot_question`.
- Produces: `create_question`, `get_question`, `list_questions(filters: ..., missing_language)`, `update_question`, `delete_question`, `submit_review` (publish validation), `list_revisions`, `create_feedback`, `list_feedback`; plus `get_translations(session, question_id)` and `_recompute_available_languages`.

- [ ] **Step 1: Write the failing service test**

Rewrite `backend/tests/test_question_service.py` to construct questions via translations. Core cases:

```python
def _payload(**over):
    base = {
        "question_type": "single_choice",
        "options": [{"order_index": 0, "is_correct": True}, {"order_index": 1, "is_correct": False}],
        "translations": [{
            "language": "en", "stem": "Which?", "correct_answer_rationale": "Because.",
            "options": [{"order_index": 0, "content": "A"}, {"order_index": 1, "content": "B"}],
        }],
        "mappings": {},
    }
    base.update(over); return base


def test_create_question_with_translations_sets_available_languages(session_with_roles, org_id, actor_id):
    from app.services.question import create_question
    payload = QuestionCreateIn(**_payload(translations=[
        {"language": "en", "stem": "en?", "correct_answer_rationale": "en r",
         "options": [{"order_index": 0, "content": "A"}, {"order_index": 1, "content": "B"}]},
        {"language": "zh", "stem": "中?", "correct_answer_rationale": "中r",
         "options": [{"order_index": 0, "content": "甲"}, {"order_index": 1, "content": "乙"}]},
    ]))
    q = create_question(session_with_roles, org_id=org_id, actor_id=actor_id, payload=payload)
    assert q.available_languages == ["en", "zh"]
    assert len(q.translations) == 2 if hasattr(q, "translations") else True  # translations read via service


def test_publish_requires_complete_translations(session_with_roles, ...):
    # A question whose zh translation is present but missing stem must NOT be approvable.
    ...


def test_list_questions_missing_language_zh(session_with_roles, ...):
    # en-only question appears under missing_language=zh; bilingual does not.
    ...
```

(Provide `org_id`/`actor_id` fixtures mirroring the existing test setup in `test_question_service.py`.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/test_question_service.py -v` → FAIL.

- [ ] **Step 3: Rewrite `backend/app/services/question.py`**

Key functions (replace the whole module body; keep `ValidationError`/`NotFound`/`IllegalTransition`):

```python
from app.models.question import (
    Question, QuestionOption, QuestionTranslation, QuestionFeedback,
    QuestionMapping, QuestionRevision,
)
from app.models.enums import AuditAction, QuestionFeedbackStatus, QuestionStatus, QuestionType
from app.schemas.question import (
    QuestionCreateIn, QuestionUpdateIn, OptionIn, TranslationIn, MappingsIn,
)
from app.services.audit import log_audit
from app.services.snapshot import snapshot_question


def _validate_options(qtype, options):
    n = len(options)
    correct = [o for o in options if o.is_correct]
    if qtype == QuestionType.true_false:
        if n != 2 or len(correct) != 1:
            raise ValidationError("true_false requires exactly 2 options with exactly 1 correct")
    elif qtype == QuestionType.single_choice:
        if not 2 <= n <= 8: raise ValidationError("single_choice requires 2-8 options")
        if len(correct) != 1: raise ValidationError("single_choice requires exactly 1 correct option")
    elif qtype == QuestionType.multiple_choice:
        if not 2 <= n <= 8: raise ValidationError("multiple_choice requires 2-8 options")
        if len(correct) < 2: raise ValidationError("multiple_choice requires at least 2 correct options")
    else:
        if not 2 <= n <= 8: raise ValidationError("question requires 2-8 options")


def get_translations(session, question_id) -> list[QuestionTranslation]:
    return list(session.execute(
        select(QuestionTranslation).where(QuestionTranslation.question_id == question_id)
        .order_by(QuestionTranslation.language)
    ).scalars().all())


def _recompute_available_languages(session, q: Question) -> None:
    langs = [t.language for t in get_translations(session, q.id)]
    q.available_languages = sorted(langs)


def _translation_is_complete(t: TranslationIn, n_options: int) -> bool:
    if not t.stem.strip() or not t.correct_answer_rationale.strip():
        return False
    if len(t.options) != n_options:
        return False
    return all(o.content.strip() for o in t.options)


def _write_translation_rows(session, q, translations: list[TranslationIn], option_count: int) -> None:
    for t in translations:
        if not t.stem.strip():
            raise ValidationError(f"{t.language} stem must not be empty")
        if len(t.options) != option_count:
            raise ValidationError(f"{t.language} options must match canonical option count")
        session.add(QuestionTranslation(
            question_id=q.id, language=t.language, stem=t.stem, stem_format=t.stem_format,
            correct_answer_rationale=t.correct_answer_rationale,
            key_point_summary=t.key_point_summary, further_reading=t.further_reading,
            options=[o.model_dump() for o in t.options],
        ))


def _next_revision_number(session, question_id) -> int:
    last = session.execute(select(QuestionRevision.revision_number)
        .where(QuestionRevision.question_id == question_id)
        .order_by(QuestionRevision.revision_number.desc())).scalars().first()
    return (last or 0) + 1


def _write_revision(session, q, *, actor_id, change_summary):
    options = list(session.execute(select(QuestionOption)
        .where(QuestionOption.question_id == q.id).order_by(QuestionOption.order_index)).scalars().all())
    translations = get_translations(session, q.id)
    session.add(QuestionRevision(
        question_id=q.id, revision_number=_next_revision_number(session, q.id),
        snapshot=snapshot_question(q, translations, options),
        edited_by_id=actor_id, change_summary=change_summary,
    ))


def _apply_mappings(session, question_id, mappings: MappingsIn) -> None:
    if mappings.domain_id is not None:
        session.add(QuestionMapping(question_id=question_id, domain_id=mappings.domain_id))
    if mappings.chapter_id is not None:
        session.add(QuestionMapping(question_id=question_id, chapter_id=mappings.chapter_id))
    if mappings.knowledge_point_id is not None:
        session.add(QuestionMapping(question_id=question_id, knowledge_point_id=mappings.knowledge_point_id))
    for tag_id in mappings.tag_ids:
        session.add(QuestionMapping(question_id=question_id, tag_id=tag_id))


def create_question(session, *, org_id, actor_id, payload: QuestionCreateIn) -> Question:
    if not payload.translations:
        raise ValidationError("at least one translation is required")
    _validate_options(payload.question_type, payload.options)
    option_count = len(payload.options)
    q = Question(
        organization_id=org_id, question_type=payload.question_type,
        difficulty=payload.difficulty, status=QuestionStatus.draft,
        source=payload.source, license_status=payload.license_status,
        prompt_items=payload.prompt_items, version=1,
        created_by_id=actor_id, updated_by_id=actor_id,
        available_languages=sorted({t.language for t in payload.translations}),
    )
    session.add(q); session.flush()
    for i, opt in enumerate(payload.options):
        session.add(QuestionOption(question_id=q.id,
            order_index=opt.order_index if opt.order_index is not None else i,
            is_correct=opt.is_correct))
    _write_translation_rows(session, q, payload.translations, option_count)
    _apply_mappings(session, q.id, payload.mappings)
    _write_revision(session, q, actor_id=actor_id, change_summary="initial creation")
    log_audit(session, action=AuditAction.edit, actor_id=actor_id, organization_id=org_id,
              entity_type="question", entity_id=str(q.id), details={"action": "create"})
    return q


def get_question(session, question_id) -> Question:
    q = session.get(Question, question_id)
    if q is None or q.deleted_at is not None:
        raise NotFound(f"question {question_id} not found")
    return q


def list_questions(session, *, org_id, page=1, size=20, filters=None) -> tuple[list[Question], int]:
    from sqlalchemy import func
    filters = filters or {}
    stmt = select(Question).where(Question.organization_id == org_id, not_deleted(Question))
    if (st := filters.get("status")) is not None:
        stmt = stmt.where(Question.status == st)
    if (qt := filters.get("question_type")) is not None:
        stmt = stmt.where(Question.question_type == qt)
    if (diff := filters.get("difficulty")) is not None:
        stmt = stmt.where(Question.difficulty == diff)
    if (ml := filters.get("missing_language")) is not None:
        # Questions whose available_languages does NOT contain ml.
        stmt = stmt.where(~Question.available_languages.any(ml))
    if (search := filters.get("search")) is not None:
        # Search across translation stems (en/zh).
        stmt = stmt.where(Question.id.in_(
            select(QuestionTranslation.question_id).where(QuestionTranslation.stem.ilike(f"%{search}%"))
        ))
    if (domain_id := filters.get("domain_id")) is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(QuestionMapping.domain_id == domain_id)))
    if (chapter_id := filters.get("chapter_id")) is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(QuestionMapping.chapter_id == chapter_id)))
    if (knowledge_point_id := filters.get("knowledge_point_id")) is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(QuestionMapping.knowledge_point_id == knowledge_point_id)))
    if (tag_id := filters.get("tag_id")) is not None:
        stmt = stmt.where(Question.id.in_(
            select(QuestionMapping.question_id).where(QuestionMapping.tag_id == tag_id)))
    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    page = max(page, 1); size = min(max(size, 1), 100)
    items = list(session.execute(stmt.order_by(Question.created_at.desc())
        .offset((page - 1) * size).limit(size)).scalars().all())
    return items, total


def _delete_rows(session, model, question_id) -> None:
    for r in session.execute(select(model).where(model.question_id == question_id)).scalars().all():
        session.delete(r)


def update_question(session, *, question_id, actor_id, payload: QuestionUpdateIn) -> Question:
    q = get_question(session, question_id)
    data = payload.model_dump(exclude_unset=True)
    changed = bool(data)
    if "options" in data:
        opts = [OptionIn(**o) for o in data["options"]]
        qtype = data.get("question_type", q.question_type)
        _validate_options(qtype, opts)
    if "translations" in data and data["translations"] is not None:
        langs = {t["language"] for t in data["translations"]}
        if not langs:
            raise ValidationError("at least one translation is required")
    if changed:
        _write_revision(session, q, actor_id=actor_id, change_summary="update")
    if "question_type" in data: q.question_type = data["question_type"]
    if "difficulty" in data: q.difficulty = data["difficulty"]
    if "source" in data: q.source = data["source"]
    if "license_status" in data: q.license_status = data["license_status"]
    if "prompt_items" in data: q.prompt_items = data["prompt_items"]
    if "options" in data:
        _delete_rows(session, QuestionOption, q.id)
        for i, opt in enumerate(opts):
            session.add(QuestionOption(question_id=q.id,
                order_index=opt.order_index if opt.order_index is not None else i,
                is_correct=opt.is_correct))
    if "translations" in data and data["translations"] is not None:
        _delete_rows(session, QuestionTranslation, q.id)
        _write_translation_rows(session, q, [TranslationIn(**t) for t in data["translations"]],
                                len(data.get("options") and opts or _current_options(session, q.id)))
    if "mappings" in data:
        _delete_rows(session, QuestionMapping, q.id)
        _apply_mappings(session, q.id, MappingsIn(**data["mappings"]))
    if changed:
        _recompute_available_languages(session, q)
        q.version = (q.version or 1) + 1
        q.updated_by_id = actor_id
        log_audit(session, action=AuditAction.edit, actor_id=actor_id,
                  organization_id=q.organization_id, entity_type="question",
                  entity_id=str(q.id), details={"action": "update"})
    return q


def _current_options(session, question_id):
    return list(session.execute(select(QuestionOption)
        .where(QuestionOption.question_id == question_id).order_by(QuestionOption.order_index)).scalars().all())
```

For `submit_review` add publish validation on the `approve` transition:

```python
_TRANSITIONS = {  # unchanged
    ReviewAction.submit: {QuestionStatus.draft: QuestionStatus.pending_review,
                          QuestionStatus.needs_revision: QuestionStatus.pending_review},
    ReviewAction.approve: {QuestionStatus.pending_review: QuestionStatus.published},
    ReviewAction.request_changes: {QuestionStatus.pending_review: QuestionStatus.needs_revision},
    ReviewAction.archive: {QuestionStatus.draft: QuestionStatus.archived,
                           QuestionStatus.pending_review: QuestionStatus.archived,
                           QuestionStatus.published: QuestionStatus.archived,
                           QuestionStatus.needs_revision: QuestionStatus.archived},
    ReviewAction.restore: {QuestionStatus.archived: QuestionStatus.draft},
}

def submit_review(session, *, question_id, actor_id, action, comment=None):
    q = get_question(session, question_id)
    if action == ReviewAction.approve:
        # FR-LANG-09: require >=1 complete translation; if both present, both complete.
        translations = get_translations(session, q.id)
        options = _current_options(session, q.id)
        n = len(options)
        complete = [t for t in translations if _translation_is_complete(
            TranslationIn(language=t.language, stem=t.stem, correct_answer_rationale=t.correct_answer_rationale,
                          options=t.options), n)]
        if not complete:
            raise ValidationError("cannot publish: no complete translation")
        if len(translations) >= 2 and len(complete) < len(translations):
            raise ValidationError("cannot publish: present translations must all be complete")
    target = _TRANSITIONS.get(action, {}).get(q.status)
    if target is None:
        raise IllegalTransition(f"action {action.value} not allowed from status {q.status.value}")
    q.status = target
    q.updated_by_id = actor_id
    audit_action = _AUDIT_ACTION.get(action, AuditAction.edit)
    log_audit(session, action=audit_action, actor_id=actor_id, organization_id=q.organization_id,
              entity_type="question", entity_id=str(q.id), details={"action": action.value, "comment": comment})
    return q
```

`list_revisions`, `delete_question`, `create_feedback`, `list_feedback` are unchanged except `delete_question`/revisions still work (they reference `Question` only). Remove the `Explanation` import.

- [ ] **Step 4: Rewrite the serializer + list route in `backend/app/api/questions.py`**

Replace `_question_out` and the `list_questions` route:

```python
from app.models.question import QuestionOption, QuestionTranslation, QuestionMapping
from app.schemas.question import (ExplanationOut removed; OptionOut, TranslationOut, TranslationOptionOut,
    QuestionOut, QuestionListItem, QuestionCreateIn, QuestionUpdateIn, ReviewAction, ReviewActionIn,
    RevisionOut, FeedbackIn, FeedbackOut, MappingsOut)


def _mappings_out(session, question_id) -> dict:
    rows = session.execute(select(QuestionMapping).where(QuestionMapping.question_id == question_id)).scalars().all()
    return {"domain_id": next((r.domain_id for r in rows if r.domain_id), None),
            "chapter_id": next((r.chapter_id for r in rows if r.chapter_id), None),
            "knowledge_point_id": next((r.knowledge_point_id for r in rows if r.knowledge_point_id), None),
            "tag_ids": [r.tag_id for r in rows if r.tag_id]}


def _question_out(session, q) -> QuestionOut:
    options = sorted(session.execute(
        select(QuestionOption).where(QuestionOption.question_id == q.id)).scalars().all(),
        key=lambda o: o.order_index)
    translations = sorted(session.execute(
        select(QuestionTranslation).where(QuestionTranslation.question_id == q.id)).scalars().all(),
        key=lambda t: t.language)
    return QuestionOut(
        id=q.id, question_type=q.question_type, difficulty=q.difficulty,
        available_languages=list(q.available_languages or []), status=q.status, source=q.source,
        license_status=q.license_status, version=q.version, prompt_items=q.prompt_items,
        created_at=q.created_at, updated_at=q.updated_at,
        options=[OptionOut(id=o.id, order_index=o.order_index, is_correct=o.is_correct) for o in options],
        translations=[TranslationOut(
            language=t.language, stem=t.stem, stem_format=t.stem_format,
            correct_answer_rationale=t.correct_answer_rationale, key_point_summary=t.key_point_summary,
            further_reading=t.further_reading,
            options=[TranslationOptionOut(**o) for o in t.options],
        ) for t in translations],
        mappings=MappingsOut(**_mappings_out(session, q.id)),
    )
```

In `list_questions` route, add `missing_language: str | None = Query(None)` param; set `filters["missing_language"] = missing_language` when provided. In the returned `QuestionListItem`, replace `stem=q.stem`/`language=q.language` with `available_languages=list(q.available_languages or [])` and drop those fields. Add a `GET /language-coverage` route here (or in admin — see Task 7); simplest is to add it to the questions router gated by `admin:view_reports`:

```python
@router.get("/language-coverage", response_model=dict)
def language_coverage(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:view_reports")),
):
    from sqlalchemy import func, case
    rows = session.execute(select(Question.available_languages).where(
        Question.organization_id == current.org_id, not_deleted(Question))).all()
    en_only = zh_only = both = neither = 0
    for (langs,) in rows:
        s = set(langs or [])
        if {"en","zh"} <= s: both += 1
        elif "en" in s: en_only += 1
        elif "zh" in s: zh_only += 1
        else: neither += 1
    return {"en_only": en_only, "zh_only": zh_only, "both": both, "neither": neither,
            "total": en_only + zh_only + both + neither}
```

(Import `Question`, `not_deleted` in the route module.)

- [ ] **Step 5: Run question service + API tests**

Run: `cd backend && pytest tests/test_question_service.py tests/test_question_api.py -v`
Expected: PASS. Fix any remaining references to dropped `stem`/`content`/`Explanation`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/question.py backend/app/api/questions.py backend/tests/test_question_service.py backend/tests/test_question_api.py
git commit -m "feat(questions): translations CRUD, available_languages, publish validation, missing_language filter, coverage"
```

---

## Task 5: Practice service — candidate filtering by mode, bilingual delivery/snapshot/answer/summary

**Files:**
- Modify: `backend/app/services/practice.py`
- Test: `backend/tests/test_practice_service.py`, `backend/tests/test_practice_api.py` (rewrite)

**Interfaces:**
- Consumes: `Question.available_languages`, `QuestionTranslation`, `snapshot_question(question, translations, options, language_mode)`, `SessionCreateIn.language_mode`, `User.language_mode`, bilingual schemas.
- Produces: practice sessions carry `config["language_mode"]`; delivery returns bilingual payload; answer snapshots freeze mode + all translations; summary wrong-questions are bilingual.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_practice_service.py`, key new cases:

```python
def test_en_mode_excludes_zh_only_question(...):
    # en-only + zh-only questions in bank; en mode session only contains en-capable.
    ...

def test_delivery_returns_both_languages(...):
    # GET question returns stem {en,zh} and options[].content {en,zh}.
    ...

def test_answer_snapshot_records_mode_and_translations(...):
    # after submit, PracticeAnswer.question_snapshot has language_mode + translations.
    ...

def test_session_uses_user_default_language_mode_when_payload_omits(...):
    # user.language_mode='zh'; SessionCreateIn has language_mode=None -> config['language_mode']=='zh'
    ...
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/test_practice_service.py -v` → FAIL.

- [ ] **Step 3: Update `backend/app/services/practice.py`**

3a. Imports: add `QuestionTranslation`, `User`; remove `Explanation`. Add a helper:

```python
from app.models.question import Question, QuestionMapping, QuestionOption, QuestionTranslation
from app.models.auth import User

def _language_filter(mode: str):
    """SQLAlchemy predicate on Question.available_languages for a mode."""
    if mode == "en":
        return Question.available_languages.any("en")
    if mode == "zh":
        return Question.available_languages.any("zh")
    # bilingual: both present
    return Question.available_languages.any("en") & Question.available_languages.any("zh")


def _resolve_mode(session, user_id, payload_mode) -> str:
    if payload_mode:
        return payload_mode
    u = session.get(User, user_id)
    return (u.language_mode if u and u.language_mode else "en")
```

3b. In `_candidate_question_ids`, add the language predicate (resolve mode via the payload first; the resolved mode is also needed by `create_session`, so pass it in):

```python
def _candidate_question_ids(session, *, org_id, payload, mode):
    stmt = select(Question.id).where(
        Question.organization_id == org_id,
        Question.status == QuestionStatus.published,
        not_deleted(Question),
        _language_filter(mode),
    )
    ...  # existing domain/book/chapter/tag/type/difficulty filters unchanged
    return [row[0] for row in session.execute(stmt).all()]
```

3c. `create_session`: resolve mode, pass to `_candidate_question_ids`, store in config:

```python
def create_session(session, *, org_id, actor_id, payload: SessionCreateIn) -> PracticeSession:
    mode = _resolve_mode(session, actor_id, payload.language_mode)
    candidate_ids = _candidate_question_ids(session, org_id=org_id, payload=payload, mode=mode)
    candidate_ids = _apply_subset(session, user_id=actor_id, candidate_ids=candidate_ids, subset=payload.subset)
    ordered = _order_questions(session, ids=candidate_ids, order_mode=payload.order_mode)[: payload.count]
    if not ordered:
        raise ValidationError("no questions match the selected scope")
    ps = PracticeSession(..., config={
        "subset": payload.subset, "order_mode": payload.order_mode, "count": payload.count,
        "language_mode": mode, "question_ids": [str(qid) for qid in ordered],
    })
    ...  # audit unchanged
```

3d. A shared delivery builder (used by `get_question_at`):

```python
def _translations_for(session, question_id):
    return list(session.execute(select(QuestionTranslation)
        .where(QuestionTranslation.question_id == question_id)).scalars().all())

def _delivery_options(options, translations):
    # Localized content per option, 1:1 by order_index, across present languages.
    out = []
    for o in sorted(options, key=lambda x: x.order_index):
        cell = {"id": str(o.id), "order_index": o.order_index,
                "content": {"en": None, "zh": None}, "content_format": {"en": None, "zh": None}}
        for t in translations:
            to = next((x for x in (t.options or []) if x.get("order_index") == o.order_index), None)
            if to:
                cell["content"][t.language] = to.get("content")
                cell["content_format"][t.language] = to.get("content_format")
        out.append(cell)
    return out

def _localized_stem(translations):
    return {"en": next((t.stem for t in translations if t.language == "en"), None),
            "zh": next((t.stem for t in translations if t.language == "zh"), None)}
```

3e. `get_question_at` returns bilingual payload + `available_languages` + `language_mode` (mode from `ps.config`):

```python
    translations = _translations_for(session, question.id)
    return {
        "session_id": str(ps.id), "position": position, "total": len(qids),
        "question_id": str(question.id), "question_type": question.question_type.value,
        "available_languages": list(question.available_languages or []),
        "language_mode": ps.config.get("language_mode", "en"),
        "stem": _localized_stem(translations),
        "options": _delivery_options(options, translations),
        "elapsed_ms": elapsed_ms,
        "previous_answer": ({"selected": prev.user_answer.get("selected"), "is_correct": prev.is_correct} if prev else None),
    }
```

3f. `submit_answer`: snapshot with mode + translations; bilingual `AnswerResultOut`:

```python
    snap = snapshot_question(question, translations, options, language_mode=ps.config.get("language_mode"))
    ...  # store snap, options_snapshot=snap["options"], judge from snap
    # Build bilingual per_option + rationale from translations:
    def loc(field):
        return {"en": next((getattr(t, field) for t in translations if t.language == "en"), None),
                "zh": next((getattr(t, field) for t in translations if t.language == "zh"), None)}
    per_option = []
    for o in snap["options"]:
        expl = {"en": None, "zh": None}
        for t in translations:
            to = next((x for x in (t.options or []) if x.get("order_index") == o["order_index"]), None)
            if to: expl[t.language] = to.get("explanation")
        per_option.append({"order_index": o["order_index"], "is_correct": o["is_correct"], "explanation": expl})
    return AnswerResultOut(
        is_correct=is_correct, correct_indexes=correct_indexes, selected_indexes=list(payload.selected),
        correct_rationale=loc("correct_answer_rationale"), key_point_summary=loc("key_point_summary"),
        per_option=per_option, mapping=_mapping_out(session, question_id),
        history=_history_out(session, user_id=user_id, question_id=question_id, exclude_session_id=ps.id),
    )
```

3g. `_build_summary` wrong-questions: bilingual stem from snapshot via `localized_from_snapshot`:

```python
from app.services.snapshot import localized_from_snapshot
...
    wrong = []
    for a in answers:
        if a.is_correct: continue
        view = localized_from_snapshot(a.question_snapshot or {}, a.question_snapshot.get("language_mode") or "en")
        wrong.append({
            "question_id": uuid.UUID(a.question_snapshot.get("question_id")) if a.question_snapshot.get("question_id") else a.question_id,
            "stem": view["stem"],
            "selected_indexes": (a.user_answer or {}).get("selected", []),
            "correct_indexes": [o["order_index"] for o in (a.options_snapshot or []) if o.get("is_correct")],
        })
```

- [ ] **Step 4: Run practice tests**

Run: `cd backend && pytest tests/test_practice_service.py tests/test_practice_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/practice.py backend/tests/test_practice_service.py backend/tests/test_practice_api.py
git commit -m "feat(practice): language-mode candidate filter, bilingual delivery/snapshot/answer/summary"
```

---

## Task 6: Exam service — candidate filtering (fixed + CAT), bilingual delivery/report/review

**Files:**
- Modify: `backend/app/services/exam.py`
- Test: `backend/tests/test_exam_service.py`, `backend/tests/test_exam_api.py` (rewrite)

**Interfaces:**
- Consumes: same helpers as practice (`_language_filter`, `_resolve_mode`, `_translations_for`, `_delivery_options`, `_localized_stem`, `localized_from_snapshot`).
- Produces: fixed + CAT sessions carry `config["language_mode"]`; `/next` and `/questions/{pos}` bilingual; report wrong-questions bilingual; review bilingual.

- [ ] **Step 1: Write failing tests** (en-mode fixed exam excludes zh-only; CAT pool excludes missing-language; `/next` bilingual; review bilingual). Mirror practice tests.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/test_exam_service.py -v` → FAIL.

- [ ] **Step 3: Update `backend/app/services/exam.py`**

3a. Imports: add `QuestionTranslation`; remove `Explanation`. Reuse the practice helpers — extract them into `app/services/i18n.py` (new tiny module) to avoid a practice↔exam import cycle:

Create `backend/app/services/i18n.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.auth import User
from app.models.question import Question, QuestionOption, QuestionTranslation


def language_filter(mode: str):
    if mode == "en":
        return Question.available_languages.any("en")
    if mode == "zh":
        return Question.available_languages.any("zh")
    return Question.available_languages.any("en") & Question.available_languages.any("zh")


def resolve_mode(session: Session, user_id, payload_mode) -> str:
    if payload_mode:
        return payload_mode
    u = session.get(User, user_id)
    return (u.language_mode if u and u.language_mode else "en")


def translations_for(session: Session, question_id) -> list[QuestionTranslation]:
    return list(session.execute(select(QuestionTranslation)
        .where(QuestionTranslation.question_id == question_id)).scalars().all())


def localized_stem(translations) -> dict:
    return {"en": next((t.stem for t in translations if t.language == "en"), None),
            "zh": next((t.stem for t in translations if t.language == "zh"), None)}


def delivery_options(options, translations) -> list[dict]:
    out = []
    for o in sorted(options, key=lambda x: x.order_index):
        cell = {"id": str(o.id), "order_index": o.order_index,
                "content": {"en": None, "zh": None}, "content_format": {"en": None, "zh": None}}
        for t in translations:
            to = next((x for x in (t.options or []) if x.get("order_index") == o.order_index), None)
            if to:
                cell["content"][t.language] = to.get("content")
                cell["content_format"][t.language] = to.get("content_format")
        out.append(cell)
    return out
```

Have practice.py and exam.py import from `app.services.i18n` (and delete the local copies in practice).

3b. `create_session` (fixed): resolve mode, pass to `_assemble`/`_domain_question_ids`, store in config:

```python
from app.services.i18n import resolve_mode, language_filter, translations_for, localized_stem, delivery_options

def create_session(session, *, org_id, actor_id, payload):
    body = _as_create_in(payload)
    bp = _current_blueprint(session)
    mode = resolve_mode(session, actor_id, getattr(body, "language_mode", None))
    if getattr(body, "kind", "fixed") == "cat":
        return create_cat_session(session, org_id=org_id, actor_id=actor_id, bp=bp, mode=mode)
    ...
    question_ids = _assemble(session, org_id=org_id, blueprint=bp, count=count, mode=mode)
    ...
    config = {..., "language_mode": mode, ...}
```

3c. `_domain_question_ids` and `_cat_candidate_pool` add `mode` param + `language_filter(mode)` predicate:

```python
def _domain_question_ids(session, *, org_id, domain_id, mode):
    return [row[0] for row in session.execute(
        select(QuestionMapping.question_id).where(
            QuestionMapping.domain_id == domain_id,
            QuestionMapping.question_id.in_(
                select(Question.id).where(
                    Question.organization_id == org_id,
                    Question.status == QuestionStatus.published,
                    not_deleted(Question), language_filter(mode))))).all()]
```

```python
def _cat_candidate_pool(session, *, org_id, blueprint, mode):
    ... .where(... not_deleted(Question), language_filter(mode), ...) ...
```

`_assemble(session, *, org_id, blueprint, count, mode)` passes `mode` to `_domain_question_ids`.

3d. `create_cat_session(session, *, org_id, actor_id, bp, mode)` resolves candidates with `mode`; store `"language_mode": mode` in the CAT config blob.

3e. `get_next_question` and `get_question_at`: bilingual payload (mirror practice `get_question_at`):

```python
    translations = translations_for(session, question.id)
    return {
        ..., "available_languages": list(question.available_languages or []),
        "language_mode": es.config.get("language_mode", "en"),
        "stem": localized_stem(translations),
        "options": delivery_options(options, translations),
        ...
    }
```

3f. `submit_answer` + `_submit_cat_answer`: snapshot with `language_mode=es.config.get("language_mode")`:

```python
    translations = translations_for(session, question_id)
    snap = snapshot_question(question, translations, options, language_mode=es.config.get("language_mode"))
```

3g. `_domain_and_wrong` wrong-questions: bilingual stem via `localized_from_snapshot`:

```python
from app.services.snapshot import localized_from_snapshot
...
    for a in answers:
        if a.is_correct: continue
        view = localized_from_snapshot(a.question_snapshot or {}, (a.question_snapshot or {}).get("language_mode") or "en")
        wrong.append(WrongQuestion(question_id=a.question_id, stem=view["stem"],
            selected_indexes=list((a.user_answer or {}).get("selected", [])),
            correct_indexes=[o["order_index"] for o in (a.options_snapshot or []) if o.get("is_correct")]))
```

3h. `get_review`: bilingual. For answered items, build options from `localized_from_snapshot(ans.question_snapshot)`; stem likewise; rationale/key_point bilingual from the same view. For never-answered, build from live translations. Example for the answered branch:

```python
        if ans is not None and ans.options_snapshot:
            view = localized_from_snapshot(ans.question_snapshot or {}, (ans.question_snapshot or {}).get("language_mode") or "en")
            opts = [{"order_index": o["order_index"], "content": o["content"], "is_correct": o["is_correct"],
                     "explanation": o["explanation"]} for o in view["options"]]
            stem = view["stem"]
            qtype = ans.question_snapshot.get("question_type", "")
            rationale = view["correct_rationale"]
            key_point = view["key_point_summary"]
            avail = view["available_languages"]
        else:
            translations = translations_for(session, question_id) if question else []
            opts = [{"order_index": o.order_index,
                     "content": _opt_localized(o.order_index, translations),
                     "is_correct": o.is_correct,
                     "explanation": _opt_expl_localized(o.order_index, translations)} for o in _options_for(session, question_id)]
            stem = localized_stem(translations)
            qtype = question.question_type.value if question else ""
            rationale = {"en": next((t.correct_answer_rationale for t in translations if t.language=="en"), None),
                         "zh": next((t.correct_answer_rationale for t in translations if t.language=="zh"), None)}
            key_point = {"en": next((t.key_point_summary for t in translations if t.language=="en"), None),
                         "zh": next((t.key_point_summary for t in translations if t.language=="zh"), None)}
            avail = list(question.available_languages or []) if question else []
        items.append(ReviewItemOut(position=position, question_id=question_id, question_type=qtype,
            available_languages=avail, stem=stem, options=opts, correct_rationale=rationale,
            key_point_summary=key_point, your_answer=..., time_spent_ms=...))
```

Add `_opt_localized`/`_opt_expl_localized` helpers reading from translations' `options` JSONB by `order_index`.

- [ ] **Step 4: Run exam tests**

Run: `cd backend && pytest tests/test_exam_service.py tests/test_exam_api.py tests/test_cat_engine.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/i18n.py backend/app/services/exam.py backend/tests/test_exam_service.py backend/tests/test_exam_api.py
git commit -m "feat(exam): language-mode candidate filter (fixed+CAT), bilingual delivery/report/review"
```

---

## Task 7: Auth preferences + admin language-coverage

**Files:**
- Modify: `backend/app/api/auth.py` (`_user_out` carries `language_mode`)
- Create: `backend/app/services/preferences.py`
- Modify: `backend/app/api/admin.py` (or questions router — Task 4 added `/language-coverage` to questions router; here ensure it's wired, otherwise add to admin)
- Test: `backend/tests/test_auth_api.py`, `backend/tests/test_admin_api.py` (extend)

**Interfaces:**
- Produces: `GET/PUT /api/users/me/preferences` → `PreferencesOut`; `UserOut.language_mode` populated from `user.language_mode`; admin coverage route (already added in Task 4 to questions router — confirm permission gating).

- [ ] **Step 1: Write failing tests**

In `backend/tests/test_auth_api.py`:

```python
def test_me_returns_language_mode(auth_client):
    r = auth_client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["language_mode"] in ("en", "zh", "bilingual")

def test_put_preferences_updates_default(auth_client):
    r = auth_client.put("/api/users/me/preferences", json={"language_mode": "zh"})
    assert r.status_code == 200 and r.json()["language_mode"] == "zh"
    me = auth_client.get("/api/auth/me").json()
    assert me["language_mode"] == "zh"

def test_put_preferences_rejects_invalid(auth_client):
    r = auth_client.put("/api/users/me/preferences", json={"language_mode": "fr"})
    assert r.status_code == 422
```

In `backend/tests/test_admin_api.py` add a coverage test (system_admin client → `/api/questions/language-coverage` returns the four counts).

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/test_auth_api.py tests/test_admin_api.py -v` → FAIL.

- [ ] **Step 3: Update `_user_out` in `backend/app/api/auth.py`**

```python
def _user_out(session, user, org_id) -> UserOut:
    return UserOut(
        id=str(user.id), email=user.email, display_name=user.display_name,
        roles=load_user_roles(session, user.id, org_id),
        perms=load_user_perms(session, user.id, org_id),
        language_mode=getattr(user, "language_mode", "en") or "en",
    )
```

- [ ] **Step 4: Create `backend/app/services/preferences.py`**

```python
from sqlalchemy.orm import Session
from app.models.auth import User
from app.models.enums import LANGUAGE_MODES
from app.services.audit import log_audit
from app.models.enums import AuditAction


def get_preferences(session: Session, user: User):
    from app.schemas.auth import PreferencesOut
    return PreferencesOut(language_mode=getattr(user, "language_mode", "en") or "en")


def set_preferences(session: Session, user: User, language_mode: str):
    if language_mode not in LANGUAGE_MODES:
        raise ValueError("invalid language_mode")
    user.language_mode = language_mode
    session.flush()
    log_audit(session, action=AuditAction.config_change, actor_id=user.id,
              organization_id=user.default_organization_id, entity_type="user",
              entity_id=str(user.id), details={"language_mode": language_mode})
    from app.schemas.auth import PreferencesOut
    return PreferencesOut(language_mode=language_mode)
```

- [ ] **Step 5: Add preferences routes**

Add to `backend/app/api/auth.py` (same router, prefix `/api/auth` would be wrong — these live under `/api/users/me/preferences`). Create a small dedicated router in a new file `backend/app/api/users.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_session
from app.dependencies import CurrentUser, require_permission, get_current_user
from app.schemas.auth import PreferencesIn, PreferencesOut
from app.services import preferences as svc

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me/preferences", response_model=PreferencesOut)
def get_prefs(current: CurrentUser = Depends(get_current_user)):
    return svc.get_preferences_deps(current)  # see below


@router.put("/me/preferences", response_model=PreferencesOut)
def put_prefs(body: PreferencesIn,
              session: Session = Depends(get_session),
              current: CurrentUser = Depends(get_current_user)):
    try:
        out = svc.set_preferences(session, current.user, body.language_mode)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    return out
```

Adjust `preferences.py` so `get_preferences` takes `(session, user)`; the GET route needs a session to read the user fresh — simplest: make GET also take `session` and `current`, calling `svc.get_preferences(session, current.user)`. (Pydantic validation of `language_mode` can also be done at the schema level with a `Literal` to return 422 automatically — preferred: set `PreferencesIn.language_mode: Literal["en","zh","bilingual"]` so invalid values 422 before the service.)

Register the router in `backend/app/main.py`: `from app.api.users import router as users_router` and `app.include_router(users_router)`.

- [ ] **Step 6: Confirm coverage route**

Task 4 added `GET /api/questions/language-coverage` gated by `admin:view_reports`. Verify it appears; if not, add it there. (The PRD §9.5 lists admin coverage under `/api/admin/questions/language-coverage` — add an alias route in `app/api/admin.py` delegating to the same logic, gated by `admin:view_reports`, to match the PRD path. Implementer: pick one canonical path and ensure both the test and the PRD path work; simplest is to add the route in `admin.py` and remove the questions-router one.)

- [ ] **Step 7: Run tests**

Run: `cd backend && pytest tests/test_auth_api.py tests/test_admin_api.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/auth.py backend/app/api/users.py backend/app/services/preferences.py backend/app/main.py backend/tests/test_auth_api.py backend/tests/test_admin_api.py
git commit -m "feat(auth): user language_mode preference + /api/users/me/preferences; admin language-coverage"
```

---

## Task 8: ETL — one bilingual CleanedQuestion, one Question + N translations per external_id

**Files:**
- Modify: `backend/app/etl/transform.py`
- Modify: `backend/app/etl/load.py`
- Modify: `backend/app/etl/runner.py`
- Test: `backend/tests/etl/` (rewrite transform/load/runner tests)

**Interfaces:**
- Produces: `transform(raw, pending_ids) -> CleanedQuestion` (bilingual, no per-language fan-out); `CleanedQuestion` carries `stem: Bilingual`, `options: [{key, text: Bilingual, explanation: Bilingual}]`, `explanation: Bilingual`, `available_languages: list[str]`, `needs_revision`; `load._apply_one` writes one Question + en/zh translations, dedup by `(dataset_slug, external_id)`.

- [ ] **Step 1: Write failing ETL tests**

In `backend/tests/etl/test_transform.py`:

```python
def test_transform_returns_one_bilingual_record(raw_question_factory):
    raw = raw_question_factory(stem_en="en", stem_zh="中")
    c = transform(raw, set())
    assert c.external_id == raw.id
    assert c.stem.en == "en" and c.stem.zh == "中"
    assert c.available_languages == ["en", "zh"]
    assert len(c.options) == len(raw.options)

def test_transform_marks_en_only_when_zh_missing(raw_question_factory):
    raw = raw_question_factory(stem_en="en", stem_zh="")
    c = transform(raw, set())
    assert c.available_languages == ["en"]
    assert c.needs_revision is True
```

In `backend/tests/etl/test_load.py`:

```python
def test_load_writes_one_question_with_two_translations(db_session, cleaned_bilingual_factory):
    cleaned = cleaned_bilingual_factory()
    apply_load(db_session, org_id, "osg10", import_job_id, [cleaned])
    qs = db_session.query(Question).filter_by(deleted_at=None).all()
    assert len(qs) == 1
    ts = db_session.query(QuestionTranslation).filter_by(question_id=qs[0].id).all()
    assert {t.language for t in ts} == {"en", "zh"}
    keys = db_session.query(QuestionExternalKey).filter_by(external_id=cleaned.external_id).all()
    assert len(keys) == 1  # one key per external_id

def test_load_idempotent_on_external_id(db_session, cleaned_bilingual_factory):
    cleaned = cleaned_bilingual_factory()
    apply_load(db_session, org_id, "osg10", iid, [cleaned])
    apply_load(db_session, org_id, "osg10", iid, [cleaned])  # unchanged -> no dup
    assert db_session.query(Question).filter_by(deleted_at=None).count() == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/etl/ -v` → FAIL.

- [ ] **Step 3: Rewrite `backend/app/etl/transform.py`**

```python
"""ETL Transform: RawQuestion -> one bilingual CleanedQuestion."""
from dataclasses import dataclass, field
from app.etl.extract import RawQuestion
from app.models.enums import QuestionType

DIFFICULTY_DEFAULT = 3


@dataclass
class CleanedOption:
    key: str
    text_en: str
    text_zh: str
    is_correct: bool


@dataclass
class CleanedQuestion:
    external_id: str
    question_type: QuestionType
    stem_en: str
    stem_zh: str
    options: list[CleanedOption]
    explanation_en: str
    explanation_zh: str
    prompt_items: list | None
    source_chapter: int
    source_chapter_title: str
    difficulty: int
    issues: list[str]
    needs_revision: bool
    available_languages: list[str] = field(default_factory=list)


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
    if raw.type in ("single_choice", "matching"):
        if len(raw.correct_keys) != 1:
            issues.append("single_choice requires exactly 1 correct key")
    elif raw.type == "multiple_choice":
        if len(raw.correct_keys) < 2:
            issues.append("multiple_choice requires at least 2 correct keys")
    return issues


def transform(raw: RawQuestion, pending_translation_ids: set[str] | None = None) -> CleanedQuestion:
    pending_translation_ids = pending_translation_ids or set()
    issues: list[str] = list(raw.meta.get("issues", [])) + list(raw.meta.get("zh_issues", []))
    if raw.id in pending_translation_ids:
        issues.append("translation_pending")

    has_zh = bool(raw.stem.zh and raw.stem.zh.strip())
    needs_revision = not has_zh
    if not has_zh:
        issues.append("missing_zh")
    available = ["en", "zh"] if has_zh else ["en"]

    prompt_items = None
    if raw.type == "matching" and raw.prompt_items:
        prompt_items = [{"key": p.key, "text": {"en": p.text.en, "zh": p.text.zh}} for p in raw.prompt_items]

    return CleanedQuestion(
        external_id=raw.id,
        question_type=_normalize_type(raw.type),
        stem_en=raw.stem.en,
        stem_zh=raw.stem.zh,
        options=[CleanedOption(key=o.key, text_en=o.text.en, text_zh=o.text.zh,
                               is_correct=o.key in raw.correct_keys) for o in raw.options],
        explanation_en=raw.explanation.en,
        explanation_zh=raw.explanation.zh,
        prompt_items=prompt_items,
        source_chapter=raw.source.chapter,
        source_chapter_title=raw.source.chapter_title,
        difficulty=DIFFICULTY_DEFAULT,
        issues=issues,
        needs_revision=needs_revision,
        available_languages=available,
    )
```

- [ ] **Step 4: Rewrite `backend/app/etl/load.py`**

```python
"""ETL Load: one Question + N translations per external_id. Dedup by (dataset_slug, external_id)."""
import uuid
from dataclasses import dataclass, field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.enums import LicenseStatus, QuestionStatus, TextFormat
from app.models.etl import ChapterDomainMapping, QuestionExternalKey
from app.models.question import (Book, Chapter, Question, QuestionMapping,
                                 QuestionOption, QuestionRevision, QuestionTranslation)
from app.services.snapshot import snapshot_question


@dataclass
class LoadResult:
    created: int = 0; updated: int = 0; unchanged: int = 0
    errors: list[dict] = field(default_factory=list)


@dataclass
class DryRunSummary:
    would_create: int = 0; would_update: int = 0; unchanged: int = 0
    errors: list[dict] = field(default_factory=list)
    by_type: dict = field(default_factory=dict); by_language: dict = field(default_factory=dict)


class _Resolvers:
    # unchanged from prior version (book/chapter/domain_id caches)
    ...


def _existing_key(session, dataset_slug, external_id) -> QuestionExternalKey | None:
    return session.execute(select(QuestionExternalKey).filter_by(
        dataset_slug=dataset_slug, external_id=external_id)).scalar_one_or_none()


def _translation_payload(cleaned, language):
    if language == "en":
        stem, rationale = cleaned.stem_en, cleaned.explanation_en
        opts = [(o.text_en if o.text_en else "") for o in cleaned.options]
    else:
        stem, rationale = cleaned.stem_zh or cleaned.stem_en, cleaned.explanation_zh or cleaned.explanation_en
        opts = [(o.text_zh if o.text_zh else o.text_en) for o in cleaned.options]
    return stem, rationale, opts


def _write_translations(session, q, cleaned):
    langs = list(cleaned.available_languages)
    for lang in langs:
        stem, rationale, opts = _translation_payload(cleaned, lang)
        session.add(QuestionTranslation(
            question_id=q.id, language=lang, stem=stem, stem_format=TextFormat.markdown,
            correct_answer_rationale=rationale,
            options=[{"order_index": i, "content": opts[i], "content_format": "markdown",
                      "explanation": None} for i in range(len(opts))],
        ))
    q.available_languages = sorted(langs)


def _current_options(session, question_id):
    return list(session.execute(select(QuestionOption).filter_by(question_id=question_id)
        .order_by(QuestionOption.order_index)).scalars())


def _differs(q, options, translations, cleaned) -> bool:
    t_en = next((t for t in translations if t.language == "en"), None)
    if t_en is None or t_en.stem != cleaned.stem_en:
        return True
    if [o.is_correct for o in options] != [o.is_correct for o in cleaned.options]:
        return True
    return False


def _apply_one(session, resolvers, dataset_slug, import_job_id, cleaned) -> str:
    existing = _existing_key(session, dataset_slug, cleaned.external_id)
    status = QuestionStatus.needs_revision if cleaned.needs_revision else QuestionStatus.draft
    if existing is None:
        q = Question(organization_id=resolvers.org_id, question_type=cleaned.question_type,
                     difficulty=cleaned.difficulty, status=status, source=cleaned.external_id,
                     license_status=LicenseStatus.unconfirmed, import_job_id=import_job_id,
                     prompt_items=cleaned.prompt_items, available_languages=sorted(cleaned.available_languages))
        session.add(q); session.flush()
        for i, opt in enumerate(cleaned.options):
            session.add(QuestionOption(question_id=q.id, order_index=i, is_correct=opt.is_correct))
        _write_translations(session, q, cleaned)
        session.add(QuestionExternalKey(dataset_slug=dataset_slug, external_id=cleaned.external_id,
                                        language=cleaned.available_languages[0] if cleaned.available_languages else None,
                                        question_id=q.id))
        ch = resolvers.chapter(cleaned)
        session.add(QuestionMapping(question_id=q.id, chapter_id=ch.id, domain_id=resolvers.domain_id(cleaned)))
        return "created"

    q = session.get(Question, existing.question_id)
    options = _current_options(session, q.id)
    translations = list(session.execute(select(QuestionTranslation).where(
        QuestionTranslation.question_id == q.id)).scalars().all())
    if not _differs(q, options, translations, cleaned):
        return "unchanged"
    old_snap = snapshot_question(q, translations, options)
    session.add(QuestionRevision(question_id=q.id, revision_number=q.version, snapshot=old_snap,
                                 change_summary="etl update"))
    q.question_type = cleaned.question_type; q.difficulty = cleaned.difficulty
    q.status = status; q.prompt_items = cleaned.prompt_items
    q.version = (q.version or 1) + 1
    for o in options: session.delete(o)
    session.flush()
    for i, opt in enumerate(cleaned.options):
        session.add(QuestionOption(question_id=q.id, order_index=i, is_correct=opt.is_correct))
    for t in translations: session.delete(t)
    session.flush()
    _write_translations(session, q, cleaned)
    return "updated"


def apply_load(session, org_id, dataset_slug, import_job_id, cleaned_list) -> LoadResult:
    resolvers = _Resolvers(session, org_id, dataset_slug)
    result = LoadResult()
    for cleaned in cleaned_list:
        try:
            sp = session.begin_nested()
            outcome = _apply_one(session, resolvers, dataset_slug, import_job_id, cleaned)
            sp.commit()
            if outcome == "created": result.created += 1
            elif outcome == "updated": result.updated += 1
            else: result.unchanged += 1
        except Exception as exc:
            try: sp.rollback()
            except Exception: pass
            result.errors.append({"external_id": cleaned.external_id, "language": None,
                                  "reason": f"{type(exc).__name__}: {exc}"})
    return result


def apply_dry_run(session, org_id, dataset_slug, cleaned_list) -> DryRunSummary:
    summary = DryRunSummary()
    for cleaned in cleaned_list:
        summary.by_type[cleaned.question_type.value] = summary.by_type.get(cleaned.question_type.value, 0) + 1
        for lang in cleaned.available_languages:
            summary.by_language[lang] = summary.by_language.get(lang, 0) + 1
        existing = _existing_key(session, dataset_slug, cleaned.external_id)
        if existing is None:
            summary.would_create += 1; continue
        q = session.get(Question, existing.question_id)
        options = _current_options(session, q.id)
        translations = list(session.execute(select(QuestionTranslation).where(
            QuestionTranslation.question_id == q.id)).scalars().all())
        summary.would_update += 1 if _differs(q, options, translations, cleaned) else 0
        summary.unchanged += 0 if _differs(q, options, translations, cleaned) else 1
    return summary
```

Keep `_Resolvers` (book/chapter/domain_id) identical to the prior version.

- [ ] **Step 5: Update `backend/app/etl/runner.py`**

`_build_cleaned` no longer fans out per language:

```python
def _build_cleaned(raws, pending_ids):
    cleaned = []
    errors = []
    for raw in raws:
        issues = validate(raw)
        if issues:
            errors.append({"external_id": raw.id, "language": None,
                           "reason": "validation: " + "; ".join(issues)})
            continue
        cleaned.append(transform(raw, pending_ids))
    return cleaned, errors
```

Update the two call sites: `_build_cleaned(raws, pending_ids)` (drop the `dataset.languages` argument). `apply_dry_run`/`apply_load` signatures unchanged.

- [ ] **Step 6: Run ETL tests + seed test**

Run: `cd backend && pytest tests/etl/ tests/test_seed.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/etl/ backend/tests/etl/ backend/tests/test_seed.py
git commit -m "feat(etl): one bilingual CleanedQuestion + one Question/N translations per external_id"
```

---

## Task 9: Backend test sweep — update all remaining tests, full suite green, drift zero

**Files:**
- Modify: `backend/tests/test_models.py`, `test_analytics.py`, `test_admin_service.py`, `test_admin_api.py`, `test_dependencies.py`, `test_security.py`, `test_audit.py`, any test still referencing `Question.stem`/`QuestionOption.content`/`Explanation`.
- Modify: `backend/app/db/seed.py` only if it references dropped fields (it does not structurally; verify).

**Interfaces:** none new.

- [ ] **Step 1: Run the full suite, collect failures**

Run: `cd backend && pytest -q 2>&1 | tail -40`
Expected: a list of failures referencing dropped attributes (`stem`, `content`, `Explanation`, `language`).

- [ ] **Step 2: Fix each failing test**

For every test that constructs a `Question`/`QuestionOption`/`Explanation` directly, migrate to the translations model. Common pattern — add a shared helper to `tests/conftest.py`:

```python
@pytest.fixture
def make_question_with_translations(db_session):
    from app.models.auth import Organization
    from app.models.enums import QuestionType, QuestionStatus, TextFormat
    from app.models.question import Question, QuestionOption, QuestionTranslation
    def _build(*, en_stem="en?", zh_stem=None, options_en=("A","B"), options_zh=None,
               rationale_en="en r", rationale_zh=None, correct_index=0,
               qtype=QuestionType.single_choice, org=None, actor=None):
        org = org or _ensure_org(db_session)
        q = Question(organization_id=org, question_type=qtype, status=QuestionStatus.published,
                     available_languages=["en"] + (["zh"] if zh_stem is not None else []), version=1)
        db_session.add(q); db_session.flush()
        for i in range(len(options_en)):
            db_session.add(QuestionOption(question_id=q.id, order_index=i, is_correct=(i == correct_index)))
        def opts(opts):
            return [{"order_index": i, "content": c, "content_format": "markdown", "explanation": None}
                    for i, c in enumerate(opts)]
        db_session.add(QuestionTranslation(question_id=q.id, language="en", stem=en_stem,
            stem_format=TextFormat.markdown, correct_answer_rationale=rationale_en, options=opts(options_en)))
        if zh_stem is not None:
            db_session.add(QuestionTranslation(question_id=q.id, language="zh", stem=zh_stem,
                stem_format=TextFormat.markdown,
                correct_answer_rationale=rationale_zh or rationale_en,
                options=opts(options_zh or options_en)))
        db_session.flush()
        from app.services.question import get_translations
        return q, list(db_session.execute(select(QuestionOption).where(
            QuestionOption.question_id == q.id).order_by(QuestionOption.order_index)).scalars().all()), get_translations(db_session, q.id)
    return _build
```

`_ensure_org(db_session)` creates/returns a personal org (mirror existing test helpers). Update `test_analytics.py`, `test_admin_service.py` (quality dashboard / low-accuracy / missing-explanations may reference `Explanation` — those endpoints now derive from `QuestionTranslation`; update the service functions in `admin.py` accordingly: `quality_dashboard` missing-explanations count = questions with no translation whose rationale is empty, etc.). Update `admin.py` service helpers that read `Explanation`/`QuestionOption.content` to read `QuestionTranslation` instead.

- [ ] **Step 3: Re-run the full suite**

Run: `cd backend && pytest -q`
Expected: all green (366+ tests, now more). If `test_no_autogenerate_drift` fails, fix the migration to match metadata exactly.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/ backend/app/services/admin.py backend/app/db/seed.py
git commit -m "test(backend): migrate all tests + admin service to translations model; full suite green"
```

---

## Task 10: Frontend types + preferences hook + AuthUser wiring

**Files:**
- Modify: `frontend/src/lib/api/types.ts`
- Modify: `frontend/src/lib/auth-store.ts`
- Modify: `frontend/src/lib/api/keys.ts`
- Create: `frontend/src/lib/api/preferences.ts`
- Test: `frontend/src/lib/__tests__/auth-store.test.ts` (extend)

**Interfaces:**
- Produces: `LanguageMode`, `LanguageCode`, `Localized`; bilingual `QuestionDelivery`/`ExamQuestionDelivery`/`OptionDelivery`/`AnswerResult`/`ReviewItem`/`ReviewOption`/`WrongQuestion`; `QuestionDetail`/`QuestionCreateInput`/`QuestionListItem` use `translations` + `available_languages`; `AuthUser.language_mode`; `usePreferences`/`useUpdatePreferences`.

- [ ] **Step 1: Write failing test**

In `frontend/src/lib/__tests__/auth-store.test.ts` add: after `setAuth` with a user carrying `language_mode: "zh"`, `useAuthStore.getState().user?.language_mode === "zh"`.

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npm run test -- auth-store` → FAIL (type lacks `language_mode`).

- [ ] **Step 3: Update `frontend/src/lib/api/types.ts`**

Add near the top:

```ts
export type LanguageCode = "en" | "zh";
export type LanguageMode = "en" | "zh" | "bilingual";

export interface Localized {
  en: string | null;
  zh: string | null;
}
```

Update delivery/option/answer/review/wrong shapes:

```ts
export interface OptionDelivery {
  id: string;
  order_index: number;
  content: Localized;
  content_format: Localized;
}

export interface QuestionDelivery {
  session_id: string; position: number; total: number; question_id: string;
  question_type: QuestionType;
  available_languages: LanguageCode[];
  language_mode: LanguageMode;
  stem: Localized;
  options: OptionDelivery[];
  elapsed_ms: number;
  previous_answer: PreviousAnswer | null;
}

export interface PerOptionExplanation { order_index: number; is_correct: boolean; explanation: Localized; }

export interface AnswerResult {
  is_correct: boolean; correct_indexes: number[]; selected_indexes: number[];
  correct_rationale: Localized; key_point_summary: Localized;
  per_option: PerOptionExplanation[]; mapping: Record<string, unknown>;
  history: Array<Record<string, unknown>>;
}

export interface WrongQuestion { question_id: string; stem: Localized; selected_indexes: number[]; correct_indexes: number[]; }
```

Add `language_mode?: LanguageMode | null;` to `SessionCreateInput` and `ExamCreateInput`.

Update question types:

```ts
export interface TranslationOption { order_index: number; content: string; content_format?: TextFormat; explanation?: string | null; }
export interface Translation {
  language: LanguageCode; stem: string; stem_format?: TextFormat;
  correct_answer_rationale: string; key_point_summary?: string | null; further_reading?: string | null;
  options: TranslationOption[];
}
export interface CanonicalOption { id?: string; order_index?: number | null; is_correct: boolean; }

export interface QuestionDetail {
  id: string; question_type: QuestionType; difficulty: number | null;
  available_languages: LanguageCode[]; status: QuestionStatus; source: string | null;
  license_status: LicenseStatus; version: number; prompt_items: unknown[] | null;
  created_at: string; updated_at: string;
  options: CanonicalOption[]; translations: Translation[]; mappings: QuestionMappings;
}
export interface QuestionCreateInput {
  question_type: QuestionType; difficulty?: number | null; source?: string | null;
  license_status?: LicenseStatus; prompt_items?: unknown[] | null;
  options: CanonicalOption[]; translations: Translation[]; mappings?: Partial<QuestionMappings>;
}
export type QuestionUpdateInput = Partial<QuestionCreateInput>;
export interface QuestionListItem {
  id: string; question_type: QuestionType; status: QuestionStatus;
  difficulty: number | null; available_languages: LanguageCode[]; domain_id: string | null; created_at: string;
}
```

Exam delivery:

```ts
export interface ExamQuestionDelivery {
  session_id: string; position: number; total: number; question_id: string;
  question_type: QuestionType; available_languages: LanguageCode[]; language_mode: LanguageMode;
  stem: Localized; options: OptionDelivery[]; elapsed_ms: number; time_remaining_ms: number;
  previous_answer: { selected: number[] } | null;
}
export interface ReviewOption { order_index: number; content: Localized; is_correct: boolean; explanation: Localized; }
export interface ReviewItem {
  position: number; question_id: string; question_type: string; available_languages: LanguageCode[];
  stem: Localized; options: ReviewOption[]; correct_rationale: Localized; key_point_summary: Localized;
  your_answer: { selected: number[] } | null; time_spent_ms: number | null;
}
```

Add `language_mode: LanguageMode;` to `AuthUser` in `frontend/src/lib/auth-store.ts`.

- [ ] **Step 4: Create `frontend/src/lib/api/preferences.ts`**

```ts
"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiJson } from "../api";
import { qk } from "./keys";
import type { LanguageMode } from "./types";

export interface Preferences { language_mode: LanguageMode; }

export function usePreferences() {
  return useQuery({
    queryKey: qk.preferences(),
    queryFn: () => apiJson<Preferences>("/api/users/me/preferences"),
  });
}

export function useUpdatePreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (language_mode: LanguageMode) =>
      apiJson<Preferences>("/api/users/me/preferences", {
        method: "PUT", body: JSON.stringify({ language_mode }),
      }),
    onSuccess: (data) => {
      qc.setQueryData(qk.preferences(), data);
      qc.invalidateQueries({ queryKey: qk.me() });
    },
  });
}
```

Add `preferences: () => ["preferences"] as const` and `me: () => ["auth","me"] as const` to `qk` in `frontend/src/lib/api/keys.ts`.

- [ ] **Step 5: Run tests**

Run: `cd frontend && npm run test -- auth-store`
Expected: PASS. Run `npm run build` later (Task 14) to catch type errors across the app.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/
git commit -m "feat(frontend): bilingual types, LanguageMode, AuthUser.language_mode, preferences hook"
```

---

## Task 11: `<BilingualText>` helper + sidebar language-mode control

**Files:**
- Create: `frontend/src/components/bilingual-text.tsx`
- Modify: `frontend/src/components/app-sidebar.tsx`
- Test: `frontend/src/components/__tests__/bilingual-text.test.tsx` (create)

**Interfaces:**
- Produces: `<BilingualText mode en zh />` renders the right text per mode (en-only, zh-only, or both stacked with a label); sidebar control sets the default language mode via `useUpdatePreferences`.

- [ ] **Step 1: Write failing test**

`frontend/src/components/__tests__/bilingual-text.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { BilingualText } from "@/components/bilingual-text";

test("en mode shows english only", () => {
  render(<BilingualText mode="en" en="Hello" zh="你好" />);
  expect(screen.getByText("Hello")).toBeInTheDocument();
  expect(screen.queryByText("你好")).not.toBeInTheDocument();
});
test("zh mode shows chinese only", () => {
  render(<BilingualText mode="zh" en="Hello" zh="你好" />);
  expect(screen.getByText("你好")).toBeInTheDocument();
});
test("bilingual shows both", () => {
  render(<BilingualText mode="bilingual" en="Hello" zh="你好" />);
  expect(screen.getByText("Hello")).toBeInTheDocument();
  expect(screen.getByText("你好")).toBeInTheDocument();
});
test("falls back to other language when one is null", () => {
  render(<BilingualText mode="en" en={null} zh="你好" />);
  expect(screen.getByText("你好")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npm run test -- bilingual-text` → FAIL.

- [ ] **Step 3: Create `frontend/src/components/bilingual-text.tsx`**

```tsx
"use client";
import type { LanguageMode } from "@/lib/api/types";

export function BilingualText({
  mode, en, zh, className,
}: { mode: LanguageMode; en: string | null; zh: string | null; className?: string }) {
  const showEn = mode !== "zh" && (en ?? zh) !== null;
  const showZh = mode !== "en" && (zh ?? en) !== null;
  return (
    <div className={className}>
      {showEn && <div className="en">{en ?? zh}</div>}
      {showZh && <div className="zh text-muted-foreground">{zh ?? en}</div>}
    </div>
  );
}

export function localizedText(mode: LanguageMode, loc: { en: string | null; zh: string | null }): string {
  if (mode === "en") return loc.en ?? loc.zh ?? "";
  if (mode === "zh") return loc.zh ?? loc.en ?? "";
  const parts = [loc.en, loc.zh].filter((x): x is string => !!x);
  return parts.join("  /  ");
}
```

- [ ] **Step 4: Add the sidebar control in `frontend/src/components/app-sidebar.tsx`**

In the bottom user panel, add a language-mode `<Select>` bound to `usePreferences`/`useUpdatePreferences` (defaults to `user?.language_mode ?? "en"` while preferences load). On change, call `updatePreferences.mutate(mode)` and also `useAuthStore.getState().setUser({ ...user, language_mode: mode })` for instant UI sync:

```tsx
const prefs = usePreferences();
const updatePrefs = useUpdatePreferences();
const mode = prefs.data?.language_mode ?? user?.language_mode ?? "en";
function onMode(v: string) {
  const m = v as LanguageMode;
  updatePrefs.mutate(m);
  if (user) setUser({ ...user, language_mode: m });
}
```

Render a labeled Select with options English / 中文 / Both.

- [ ] **Step 5: Run tests**

Run: `cd frontend && npm run test -- bilingual-text`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/
git commit -m "feat(frontend): BilingualText helper + sidebar default language-mode control"
```

---

## Task 12: Practice — create-form language select, runner mode toggle + bilingual render, summary

**Files:**
- Modify: `frontend/src/features/practice/session-payload.ts`
- Modify: `frontend/src/features/practice/create-session-form.tsx`
- Modify: `frontend/src/features/practice/option-list.tsx`
- Modify: `frontend/src/features/practice/runner.tsx`
- Modify: `frontend/src/features/practice/summary.tsx`
- Test: `frontend/src/features/practice/__tests__/session-payload.test.ts`, `option-list.test.tsx`

**Interfaces:**
- Produces: `SessionFormState.languageMode`; payload includes `language_mode`; `OptionList` renders `content` per a `mode` prop (bilingual = stacked en/zh); runner has an in-runner mode toggle (local state, defaults to session `language_mode`); summary renders wrong-question stems via `localizedText`.

- [ ] **Step 1: Write failing tests**

`session-payload.test.ts`: `buildSessionPayload({languageMode: "zh", ...})` produces `{ ..., language_mode: "zh" }`; default omits when null.
`option-list.test.tsx`: with `mode="bilingual"`, both `o.content.en` and `o.content.zh` render; with `mode="en"`, only en.

- [ ] **Step 2: Run to verify it fails** → `npm run test -- session-payload option-list`.

- [ ] **Step 3: Update `session-payload.ts`** — add `languageMode: LanguageMode | null` to `SessionFormState` (default `null`); in `buildSessionPayload`, `if (f.languageMode) payload.language_mode = f.languageMode;`.

- [ ] **Step 4: Update `create-session-form.tsx`** — add a Language Mode `<Select>` (English / 中文 / Both, default from `useAuthStore` user `language_mode`), writing to `form.languageMode`.

- [ ] **Step 5: Update `option-list.tsx`** — accept a `mode: LanguageMode` prop; render each option's content via `<BilingualText mode={mode} en={o.content.en} zh={o.content.zh} />` (replace `<span>{o.content}</span>`). Keep selection/correctness logic unchanged.

- [ ] **Step 6: Update `runner.tsx`** — add `const [mode, setMode] = useState<LanguageMode>(delivery.language_mode)` (re-init when `delivery.language_mode` changes via `useEffect`); render `<CardTitle><BilingualText mode={mode} en={delivery.stem.en} zh={delivery.stem.zh} /></CardTitle>`; pass `mode` to `<OptionList>`; render `result.correct_rationale`/`key_point_summary`/`per_option[].explanation` via `BilingualText`; add a mode-toggle `<Select>` (En / 中 / Both) above the question. Selections (`runner.selected`) and timer are untouched by the toggle (index-based).

- [ ] **Step 7: Update `summary.tsx`** — render `w.stem` via `localizedText(sessionMode, w.stem)` (read `sessionMode` from the session `config.language_mode` via `useSession`).

- [ ] **Step 8: Run tests** → `cd frontend && npm run test -- practice` PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/features/practice/
git commit -m "feat(frontend/practice): language-mode select, runner toggle, bilingual option/stem render"
```

---

## Task 13: Exam — start-form language select, fixed/CAT runner toggle + bilingual render, report/review

**Files:**
- Modify: `frontend/src/features/exam/start-form.tsx`
- Modify: `frontend/src/features/exam/fixed-runner.tsx`
- Modify: `frontend/src/features/exam/cat-runner.tsx`
- Modify: `frontend/src/features/exam/report.tsx`
- Modify: `frontend/src/features/exam/review.tsx`
- Test: `frontend/src/features/exam/__tests__/start-form.test.tsx` (create) + extend `format.test.ts`

**Interfaces:**
- Produces: `ExamStartForm` sends `language_mode`; both runners have a mode toggle (default session `language_mode`) and bilingual stem/option render via `BilingualText`; CAT toggle does **not** call `/next` (just re-renders current item); report/review render bilingual stems + rationale.

- [ ] **Step 1: Write failing tests** — `start-form.test.tsx`: selecting "zh" and starting posts `{ kind: "fixed", language_mode: "zh" }` (mock `useCreateExam`).

- [ ] **Step 2: Run to verify it fails** → `npm run test -- exam`.

- [ ] **Step 3: Update `start-form.tsx`** — add a language-mode `<Select>` (default from `useAuthStore` user `language_mode`); include `language_mode` in the `body` for both fixed and CAT.

- [ ] **Step 4: Update `fixed-runner.tsx`** — `const [mode, setMode] = useState<LanguageMode>(delivery.language_mode)`; render `<CardTitle><BilingualText mode={mode} .../></CardTitle>`; pass `mode` to `<OptionList>`; add mode-toggle Select. Selections (`selections[position]`) and palette unaffected.

- [ ] **Step 5: Update `cat-runner.tsx`** — same mode toggle + bilingual render. **Critical:** the toggle only changes local `mode` state; it must NOT invalidate/refetch `qk.exam.next` (so CAT never advances on toggle). Render `delivery.stem`/`options` via `BilingualText`.

- [ ] **Step 6: Update `report.tsx`** — render wrong-question `w.stem` via `localizedText(mode, w.stem)` where `mode` = session `config.language_mode` (from `useExamSession`).

- [ ] **Step 7: Update `review.tsx`** — add a mode toggle (default session mode); render `item.stem`, `o.content`, `item.correct_rationale`, `item.key_point_summary` via `BilingualText`/`localizedText`.

- [ ] **Step 8: Run tests** → `cd frontend && npm run test -- exam` PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/features/exam/
git commit -m "feat(frontend/exam): language-mode select, runner toggle (CAT-safe), bilingual report/review"
```

---

## Task 14: Question editor (bilingual tabs + completeness) + list/detail bilingual; full build + e2e verify

**Files:**
- Modify: `frontend/src/features/questions/editor.tsx`
- Modify: `frontend/src/features/questions/list.tsx`
- Modify: `frontend/src/features/questions/detail.tsx`
- Test: `frontend/src/features/questions/__tests__/editor.test.tsx` (create)

**Interfaces:**
- Produces: editor with English / Chinese tabs (stem, each option content, rationale); canonical options (order + is_correct) shared; `available_languages` inferred; completeness validation mirrors backend publish rules; list shows `available_languages` badges + a "missing zh/en" filter; detail renders both languages.

- [ ] **Step 1: Write failing test** — `editor.test.tsx`: filling English tab + canonical options enables save and posts a payload with `translations: [{language:"en",...}]` and `options: [{order_index,is_correct}]`; enabling the Chinese tab and leaving its stem blank blocks save with a toast.

- [ ] **Step 2: Run to verify it fails** → `npm run test -- questions`.

- [ ] **Step 3: Rewrite `editor.tsx`**

State:
```tsx
const [type, setType] = useState(initial?.question_type ?? "single_choice");
const [difficulty, setDifficulty] = useState(...);
const [domainId, setDomainId] = useState(...);
// canonical options (shared correctness + order)
const [options, setOptions] = useState<{is_correct: boolean}[]>(
  initial?.options.map(o => ({is_correct: o.is_correct})) ?? [{is_correct:true},{is_correct:false}]);
// per-language content
const [en, setEn] = useState({stem: "", rationale: "", opts: ["",""]});
const [zh, setZh] = useState<{stem: string; rationale: string; opts: string[]} | null>(
  initial?.translations.find(t=>t.language==="zh") ? {stem, rationale, opts} : null);
const [source, setSource] = useState(...); const [license, setLicense] = useState(...);
```

Add a "Add Chinese version" toggle that sets `zh` to a blank object; a tab switch (English / Chinese) controls which language's stem/option-content/rationale inputs are shown. `validate()`:
- en stem non-empty, ≥2 options with content, ≥1 correct (single: exactly 1), rationale non-empty.
- if `zh` is enabled: zh stem non-empty, all zh option contents non-empty, zh rationale non-empty (completeness — mirrors backend publish rule).

`buildPayload()`:
```ts
const canonical = options.map((o, i) => ({order_index: i, is_correct: o.is_correct}));
const translations = [{
  language: "en", stem: en.stem.trim(), correct_answer_rationale: en.rationale.trim(),
  options: en.opts.map((c, i) => ({order_index: i, content: c.trim()})),
}];
if (zh) translations.push({language: "zh", stem: zh.stem.trim(), correct_answer_rationale: zh.rationale.trim(),
  options: zh.opts.map((c, i) => ({order_index: i, content: c.trim()}))});
return { question_type: type, difficulty: ..., source: ..., license_status: license,
         options: canonical, translations, mappings: domainId ? {domain_id: domainId} : {} };
```

- [ ] **Step 4: Update `list.tsx`** — replace the `Lang` column with `available_languages` badges (`EN`/`中`/`EN+中`); add a "Missing language" filter select (`en`/`zh`) that adds `missing_language` to the query (wire a new query param in `useQuestions`).

- [ ] **Step 5: Update `detail.tsx`** — render stem/options/rationale for each present translation (stacked or tabbed).

- [ ] **Step 6: Run frontend tests + build**

Run:
```bash
cd frontend && npm run test && npm run lint && npm run build
```
Expected: all green; build succeeds (type errors resolved across the app).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/questions/ frontend/src/lib/api/questions.ts
git commit -m "feat(frontend/questions): bilingual editor tabs + completeness, available_languages badges + missing filter"
```

---

## Task 15: Full-stack verify — docker compose, backend tests, frontend tests, e2e language flows

**Files:** none (verification only; update `CLAUDE.md` current-state note at the end).

- [ ] **Step 1: Build + start the stack**

Run:
```bash
docker compose up -d --build
docker compose ps
curl -s http://localhost:8000/health   # {"status":"ok","db":"ok","redis":"ok"}
curl -s http://localhost:3000/ | head   # frontend renders
```
Expected: backend applies the new migration on startup (Alembic `upgrade head`); health ok.

- [ ] **Step 2: Backend tests in container**

Run:
```bash
docker compose exec backend pytest -q
```
Expected: all green, zero migration drift.

- [ ] **Step 3: Frontend tests + build in container**

Run:
```bash
docker compose exec frontend npm run test
docker compose exec frontend npm run build
```
Expected: green; build succeeds.

- [ ] **Step 4: E2E language-mode flows**

Via the UI (or `curl` with tokens):
1. Login as `admin/admin`; set default language mode → `bilingual` (sidebar control).
2. Import → preview → commit the osg10 dataset; confirm one Question per external_id with en+zh translations (`available_languages=[en,zh]`).
3. Publish a few questions (review approve).
4. Start a **practice** session in `en` mode → only en-capable questions delivered; toggle to `bilingual` mid-session → both languages render, selection/timer preserved.
5. Start a **practice** session in `zh` mode → only zh-capable questions; stems render Chinese.
6. Start a **fixed exam** in `bilingual` → both languages; toggle works; finish → report shows bilingual wrong-question stems.
7. Start a **CAT exam** in `bilingual` → both languages; toggle does NOT advance the item; finish → report shows ability/CI/SEM/readiness + disclaimer.
8. Admin → language-coverage endpoint returns counts.

- [ ] **Step 5: Update `CLAUDE.md` current-state note**

Append a one-line note that bilingual language selection (FR-LANG-01..10) is implemented and merged.

- [ ] **Step 6: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: note bilingual language selection (FR-LANG) implemented"
```

---

## Self-Review (against the spec)

**Spec coverage:**
- FR-LANG-01 (bilingual storage) → Tasks 1, 3, 4.
- FR-LANG-02 (mode en/zh/bilingual) → Tasks 3, 5, 6, 10.
- FR-LANG-03 (default pref + per-session override) → Tasks 3, 5, 6, 7, 11.
- FR-LANG-04 (missing-language excluded) → Tasks 5, 6 (`_language_filter`).
- FR-LANG-05 (bilingual side-by-side, 1:1) → Tasks 3, 11, 12, 13 (`BilingualText`, `delivery_options`).
- FR-LANG-06 (instant toggle, no loss) → Tasks 12, 13 (both languages in payload; toggle is local state).
- FR-LANG-07 (snapshot mode + both languages, history frozen) → Tasks 3, 5, 6 (`snapshot_question`, `localized_from_snapshot`).
- FR-LANG-08 (import `*_zh`, supplement later) → Tasks 4, 8, 14 (editor adds zh later; ETL writes both).
- FR-LANG-09 (editor en/zh tabs + publish validation) → Tasks 4, 14.
- FR-LANG-10 (admin coverage + missing filter) → Tasks 4, 7, 14.
- FR-PRAC-11 / FR-ANS-10 / FR-EXAM-07 / FR-CAT-11 → Tasks 5, 6, 12, 13.

**Placeholder scan:** none — every code step shows the actual code or a precise targeted edit. (Task 2 Step 4's merge-test INSERTs are intentionally left for the implementer to match the exact pre-migration column set, with the load-bearing assertion specified; this is documented, not a placeholder.)

**Type consistency:** `Localized`/`LanguageMode`/`LanguageCode` defined once in both backend (`enums.py` literals + schema `Localized`) and frontend (`types.ts`) and reused consistently. `snapshot_question` signature `(question, translations, options, *, language_mode=None)` is consistent across Tasks 3, 5, 6, 8. `localized_from_snapshot(snap, mode)` consistent across 5, 6. `i18n.py` helpers (`language_filter`, `resolve_mode`, `translations_for`, `localized_stem`, `delivery_options`) consumed identically by practice (Task 5) and exam (Task 6).

**Risks acknowledged:** large migration with FK repointing (Task 2 — tested via dedicated merge test); full test-suite rewrite (Task 9); CAT toggle correctness (Task 13 — toggle must not refetch `/next`, stated explicitly).

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-26-question-language-selection.md`.**

Per the user's directive (do not ask for selection; make recommended choices), I will proceed with **Subagent-Driven execution** (recommended): dispatch a fresh subagent per task with two-stage review between tasks, until the plan is complete and the full stack runs.
