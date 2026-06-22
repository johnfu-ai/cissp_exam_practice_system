# Sub-project E: Practice API — Design

> Derived from PRD §6.5 (FR-PRAC-01..10) and §6.6 (FR-ANS-01..09). Source of truth: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md`. P0 requirements are implemented; cheap P1s (ordering modes, notes, pause/resume) are included. Weak-point-first ordering (FR-PRAC-06) and same-KP recommendation (FR-ANS-08) are deferred to the analytics sub-project (H), which owns the data they depend on.

## Goal

Let an authenticated learner start a scoped practice session, answer one question at a time, receive immediate judgment + explanation, mark questions, and get an end-of-session summary — all with historical-integrity snapshots so later question edits never alter past answers (NFR-DATA-01).

## Scope (in / out)

**In (P0):**
- FR-PRAC-01 quick practice (system picks random published questions)
- FR-PRAC-02 scope by domain
- FR-PRAC-03 scope by book + chapter(s)
- FR-PRAC-05 custom question count (10/25/50/100/custom, capped)
- FR-PRAC-07 subset filters: all / unpracticed / wrong / bookmarked / needs-review
- FR-PRAC-09 session timing + per-question time spent
- FR-PRAC-10 end summary: accuracy, total time, per-domain breakdown, wrong-question list
- FR-ANS-01 one question per request (stem, options, progress, elapsed)
- FR-ANS-02 immediate judgment (correct/incorrect + your answer vs correct answer)
- FR-ANS-03/04 explanation (correct rationale + per-option rationale from `Explanation` + `QuestionOption.explanation`)
- FR-ANS-05 show associated domain/KP/book-chapter + the user's personal history on that question
- FR-ANS-06 bookmark / flag-review / mark-mastered / mark-questioned

**In (cheap P1):**
- FR-PRAC-06 ordering: random / sequential / easy_to_hard (weak_first deferred — needs cross-session analytics)
- FR-PRAC-08 pause / resume (record `paused_at`)
- FR-ANS-07 personal notes (already a `UserQuestionState.note` column)

**Out (later sub-projects):**
- FR-PRAC-04 KP/difficulty/type/tag as *first-class* filters — `list_questions` already supports them, so they are accepted pass-through filters but not given dedicated UI spec here.
- FR-ANS-08 same-KP recommendation + review suggestions (sub-project H).
- Fixed exam / CAT (sub-projects F, G).

## Architecture

A new service module `app/services/practice.py` owns all logic and DB access; a new router `app/api/practice.py` exposes it. Routes delegate to the service and commit the session after successful mutations (same pattern as question/taxonomy admin). Answer judging reads correctness from the **snapshot** captured at answer time, not from live options, so a judgment always matches what the learner saw.

No new bounded context. Three existing models carry the work:
- `PracticeSession` (tenant-scoped) — gains two columns: `config JSONB` (the scope/order/subset used) and `paused_at TIMESTAMPTZ`.
- `PracticeAnswer` — unchanged; already stores `question_snapshot` + `options_snapshot` + `user_answer` + `is_correct` + `time_spent_ms`.
- `UserQuestionState` — unchanged; already has `is_bookmarked`, `is_flagged_review`, `is_mastered`, `is_questioned`, `note`, `mastery_level`.

A migration adds the two columns. Tests use `Base.metadata.create_all` (not migrations), so the model change alone makes tests pass; the migration keeps the dev DB runnable.

## Data model changes

`PracticeSession` new columns:
- `config: JSONB NOT NULL DEFAULT '{}'` — `{scope, subset, count, order_mode, question_ids}`. `question_ids` is the pre-built ordered list chosen at creation time, making delivery positional and stable across pause/resume.
- `paused_at: TIMESTAMPTZ NULL` — set on pause, cleared on resume; `NULL` while actively running.

No other model changes. `PracticeAnswer.user_answer` shape is normalized to `{"selected": [<option order_index>, ...]}` for all question types (single/true_false → one element; multiple → many). Judging compares the selected set against the snapshot options' `is_correct` flags.

## Service layer (`app/services/practice.py`)

Exceptions (mirroring `taxonomy_admin`): `ValidationError(ValueError)`, `NotFound(LookupError)`, `ConflictError(ValueError)`.

**Session creation** — `create_session(session, *, org_id, actor_id, payload: SessionCreateIn) -> PracticeSession`:
1. Validate `count` (1..200), `order_mode` (one of the allowed values), `subset` (one of the allowed values).
2. Build the candidate question set: tenant-scoped, `status == published`, `not_deleted`, plus scope filters (domain_id, book_id, chapter_ids, question_type, difficulty, tag_id).
3. Apply subset filter:
   - `unpracticed` → exclude question_ids present in this user's `PracticeAnswer`.
   - `wrong` → only question_ids where the user has at least one incorrect `PracticeAnswer`.
   - `bookmarked` → only question_ids where `UserQuestionState.is_bookmarked` for this user.
   - `needs_review` → only where `is_flagged_review`.
   - `all` → no extra filter.
4. Order:
   - `random` → `ORDER BY random()`.
   - `sequential` → `ORDER BY created_at`.
   - `easy_to_hard` → `ORDER BY difficulty NULLS LAST, created_at`.
5. Limit to `count`. If fewer than `count` available, use what's available (validate ≥1, else `ValidationError`). Store the resulting `question_ids` list in `config`.
6. Create `PracticeSession(user_id, organization_id, status=in_progress, total_questions=len, config=...)`. `log_audit(action=edit, entity_type="practice_session")`. Return it.

**Delivery** — `get_question_at(session, *, session_id, position, user_id) -> dict`:
- Load session; enforce `user_id` ownership and tenant. `NotFound` if missing.
- `position` is 0-based; must be `< total_questions`. Return the live question's stem/options (without revealing correctness — `is_correct` stripped from options), the position, total, elapsed session time, and the existing `PracticeAnswer` for that position if already answered (so the UI can show prior answer on revisit). Correctness flags are NOT sent until the learner answers (FR-ANS-01).

**Answer** — `submit_answer(session, *, session_id, position, user_id, payload: AnswerIn) -> AnswerResult`:
- Load session + ownership. If `status != in_progress` → `ConflictError`. If `paused_at` set → `ConflictError` ("session paused").
- If a `PracticeAnswer` already exists for this (session, position) → `ConflictError` (no revision of submitted answers, matching exam rule; practice still lets you *revisit and view*, not re-answer within the same session).
- Load the live question + options; build `snapshot_question(q, options)`.
- Judge from the snapshot: `selected` set vs `{o.order_index for o in snapshot options if o.is_correct}`. `is_correct = (sets equal)`.
- Compute `time_spent_ms` from `payload.started_at`/`now()` (client sends `started_at` ISO ts; server clamps to ≥0).
- Persist `PracticeAnswer(session_id, user_id, question_id, question_snapshot, options_snapshot, user_answer={"selected": [...]}, is_correct, time_spent_ms)`.
- Update `session.correct_count` if correct.
- Upsert `UserQuestionState`: set `mastery_level` to `learning`/`mastered` based on correctness, `is_questioned=False` no longer needed... — minimal: set `mastery_level = mastered if is_correct else learning` (only advance, never regress on a single answer). Touch `updated_at`.
- `log_audit(action=edit, entity_type="practice_answer")`.
- Return `AnswerResult`: judgment, correct option order_indexes, the user's selected, the explanation (correct rationale + per-option rationale), the associated domain/KP/chapter (from `QuestionMapping`), and this user's prior history on the question (list of past `PracticeAnswer` is_correct + answered_at from other sessions).

**Pause/resume** — `pause_session` sets `paused_at=now()`; `resume_session` clears it. Both enforce ownership + in_progress.

**Finish** — `finish_session(session, *, session_id, user_id) -> SessionSummary`:
- Enforce ownership. If already completed, return existing summary (idempotent). Set `status=completed`, `ended_at=now()`.
- Build summary: `total_questions`, `answered_count`, `correct_count`, `accuracy`, `total_time_spent_ms` (sum of `time_spent_ms`), per-domain breakdown (`{domain_id, domain_name, answered, correct}`), wrong-question list (question_id, stem snapshot, your answer, correct answer).
- `log_audit(action=edit)`.

**UserQuestionState** — `set_question_state(session, *, user_id, question_id, payload: QuestionStateIn)`:
- Upsert `UserQuestionState` for (user, question). Apply any of `is_bookmarked`, `is_flagged_review`, `is_mastered`, `is_questioned`, `note` (all optional; `mastery_level` derived if `is_mastered` set). Tenant-check the question exists in the user's org.

## Schemas (`app/schemas/practice.py`)

`SessionCreateIn`: `subset` (enum: all/unpracticed/wrong/bookmarked/needs_review), `order_mode` (enum: random/sequential/easy_to_hard), `count` (int), optional `domain_id`, `book_id`, `chapter_ids: list[UUID]`, `question_type`, `difficulty`, `tag_id`.

`QuestionDeliveryOut`: `position`, `total`, `session_id`, `question` (stem, type, options WITHOUT is_correct), `elapsed_ms`, `previous_answer` (nullable).

`AnswerIn`: `position`, `selected: list[int]` (option order_indexes), `started_at` (datetime).

`AnswerResultOut`: `is_correct`, `correct_indexes: list[int]`, `selected_indexes: list[int]`, `explanation` (rationale + per-option), `mapping` (domain/kp/chapter), `history` (list).

`SessionSummaryOut`: `total_questions`, `answered_count`, `correct_count`, `accuracy`, `total_time_spent_ms`, `domains: list[...]`, `wrong_questions: list[...]`.

`QuestionStateIn`: all-optional `is_bookmarked`, `is_flagged_review`, `is_mastered`, `is_questioned`, `note`.

`SessionOut`: id, status, total_questions, correct_count, started_at, ended_at, paused_at, config.

## HTTP API (`app/api/practice.py`, prefix `/api/practice`)

All gated by `require_permission("practice:read")`:
- `POST /sessions` → create
- `GET /sessions/{id}` → state
- `GET /sessions/{id}/questions/{position}` → deliver
- `POST /sessions/{id}/answers` → submit (returns AnswerResult)
- `POST /sessions/{id}/pause` · `POST /sessions/{id}/resume`
- `POST /sessions/{id}/finish` → summary
- `GET /sessions/{id}/summary`
- `PUT /questions/{question_id}/state` → set marks/notes

Error mapping: `NotFound→404`, `ValidationError→422`, `ConflictError→409`. Caller commits after success.

## Error handling

- Ownership violation (session belongs to another user) → `NotFound` (404) — never leak existence.
- Tenant mismatch → `NotFound`.
- Submit to a completed/paused session → `ConflictError` (409).
- Re-answer same position → `ConflictError` (409).
- Empty candidate set → `ValidationError` (422, "no questions match the selected scope").
- Position out of range → `ValidationError` (422).

## Testing

Service-layer tests (`tests/test_practice_service.py`) on the bare `db_session` with manual org/actor/question fixtures: creation + scope/subset filtering, ordering, answer judging for single/multiple/true_false, snapshot persisted, re-answer refused, pause/resume, finish summary accuracy + domain breakdown + wrong list, user-state upsert, ownership/tenant isolation (404).

HTTP tests (`tests/test_practice_api.py`) reusing the `client` + `register_user` + token pattern from `test_question_api.py`: full happy path (create → deliver → answer → finish → summary), validation 422, conflict 409 on re-answer, 404 on other-user session, 403 for a role lacking `practice:read`, 401 without token.

Full suite + migration drift test must remain green.

## Non-functional

- NFR-DATA-01 (snapshots) — judged from snapshot.
- NFR-DATA-02 (soft delete) — `not_deleted(Question)` in candidate query.
- NFR-PERF-02 (next-question P95 < 300ms) — positional delivery from `config.question_ids`, single indexed query; no concern at this scale.
- Tenant scoping — session + question queries are org-scoped.
