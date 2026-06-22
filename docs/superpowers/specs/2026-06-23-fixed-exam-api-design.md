# Sub-project F: Fixed Exam API — Design

> Derived from PRD §6.7 (FR-EXAM-01..06), §2 (official baseline), §9.4 (exam data model). Source of truth: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md`. P0 requirements are implemented; FR-EXAM-06 (history + trend, P1) is included because it is cheap and depends only on data this sub-project produces. CAT (FR-CAT) is a separate sub-project (G).

## Goal

Let an authenticated learner start a **fixed-count** mock exam assembled automatically from the current `ExamBlueprint`'s CISSP domain weights, answer questions under a timed, feedback-free session, have the exam auto-submit when time expires, then receive a full exam report (scaled score, pass/fail, per-domain performance, time analysis, wrong-question list) and a unified post-exam review of every question with correct answers and explanations — all with historical-integrity snapshots (NFR-DATA-01).

## Scope (in / out)

**In (P0):**
- FR-EXAM-01 fixed-count mock exam (count from blueprint, optionally overridden within `[min_items, max_items]`).
- FR-EXAM-02 domain-weighted auto-assembly from the **current** `ExamBlueprint` (`ExamDomain.weight_pct`), using the largest-remainder method so per-domain counts sum exactly to the total.
- FR-EXAM-03 timed session (`blueprint.duration_minutes`); **lazy auto-submit** when the deadline elapses (enforced on every interaction + on finish).
- FR-EXAM-04 post-exam unified review: every question with the correct answer + per-option/correct rationale (no feedback during the exam).
- FR-EXAM-05 exam report: scaled score (0..`max_score`), pass/fail vs `passing_score`, accuracy, per-domain answered/correct, total + average time, wrong-question list.

**In (cheap P1):**
- FR-EXAM-06 exam history + trend: list the learner's completed exams (score/accuracy/date/passed) ordered by `started_at`.

**Out (later sub-projects):**
- CAT exam (sub-project G) — `ExamSessionKind.cat`, ability estimation, forward-only/no-skip, next-item selection, early-stop. The `ExamAnswer.ability_estimate_after`/`se_after` columns are left for G.
- Analytics dashboards / admin backoffice (sub-project H).
- Background-job time-up submission (a real scheduler). MVP uses lazy enforcement on next request + client-side countdown; acceptable per PRD MVP scope.

## Architecture

A new service module `app/services/exam.py` owns all logic and DB access; a new router `app/api/exam.py` exposes it. Routes delegate to the service and commit the session after successful mutations (same pattern as practice/question/taxonomy admin in sub-projects B–E). Answer judging reads correctness from the **snapshot** captured at answer time (`snapshot_question()`), never from live options (NFR-DATA-01).

Key behavioral difference from practice: **exam mode gives no feedback during the session.** `submit_answer` saves/overwrites the answer and returns only an acknowledgement + remaining time — no `is_correct`, no explanation. Judgment and explanations are computed at finish/review time from the stored snapshots. Answers are **revisable** until the session is finished (learner may navigate positions and resubmit); `correct_count` is recomputed from all stored answers at finish.

No new bounded context. Two existing models carry the work:
- `ExamSession` (tenant-scoped) — gains one column: `config JSONB` (`{count, question_ids, deadline_at}`).
- `ExamAnswer` — unchanged; already stores `question_snapshot` + `options_snapshot` + `user_answer` + `is_correct` + `time_spent_ms` + `answered_at`. `ability_estimate_after`/`se_after` are left NULL for fixed exams (used by G).

A migration adds the `config` column. Tests use `Base.metadata.create_all` (not migrations), so the model change alone makes tests pass; the migration keeps the dev DB runnable and the drift test green.

## Data model changes

`ExamSession` new column:
- `config: JSONB NOT NULL DEFAULT '{}'` — `{count: int, question_ids: [str, ...], deadline_at: iso8601}`. `question_ids` is the pre-built, shuffled ordered list chosen at creation time, making delivery positional and stable. `deadline_at` = `started_at + duration_minutes` (stored once to avoid clock drift; used for lazy auto-submit).

No other model changes. `ExamAnswer.user_answer` shape is `{"selected": [<option order_index>, ...]}` (same normalization as practice). Re-answer **upserts** the row for `(session_id, question_id)` — there is at most one `ExamAnswer` per question per exam.

Scaled score and pass/fail are **computed** (not stored as columns) from `correct_count`/`total_questions` + the blueprint's `max_score`/`passing_score`. To preserve historical integrity, the finish endpoint **snapshots the scoring basis** into `config` as well: `{count, question_ids, deadline_at, max_score, passing_score, duration_minutes}`. The report reads scoring from `config`, so later blueprint edits (e.g. raising `passing_score`) never change a past exam's score/pass. (This is the data-is-data-not-code rule applied to history.)

## Service layer (`app/services/exam.py`)

Exceptions (mirroring practice/taxonomy admin): `ValidationError(ValueError)`, `NotFound(LookupError)`, `ConflictError(ValueError)`.

**Blueprint resolution** — `_current_blueprint(session) -> ExamBlueprint`:
- Select the `ExamBlueprint` with `is_current=True`. Raise `ValidationError("no current exam blueprint configured")` if none (exam-config-as-data: never hardcode weights/rules).

**Domain-weighted assembly** — `_assemble(session, *, org_id, blueprint, count) -> list[uuid.UUID]`:
1. Load the blueprint's `ExamDomain` rows.
2. Per domain, compute `target = floor(count * weight_pct / 100)`; track fractional remainders. Distribute the leftover (`count - sum(targets)`) one each to the domains with the largest fractional remainder (largest-remainder method) so `sum(targets) == count`.
3. For each domain, select `target` random published tenant-scoped questions mapped to that domain (`QuestionMapping.domain_id == d.id`, `Question.status == published`, `not_deleted`). If fewer than `target` are available, take all and record the shortfall.
4. Redistribute shortfalls: iterate domains with `available < target` (deficit) and domains with `available > target` (surplus), moving questions from surplus to deficit until no deficit remains or no surplus remains.
5. If total assembled `< count`, raise `ValidationError("not enough published questions to assemble a {count}-question exam")`.
6. Shuffle the final list (so questions are not grouped by domain). Return it.

**Session creation** — `create_session(session, *, org_id, actor_id, payload: ExamCreateIn) -> ExamSession`:
1. Resolve current blueprint; load `min_items`/`max_items`/`duration_minutes`/`max_score`/`passing_score`.
2. `count = payload.count or blueprint.max_items`; validate `min_items <= count <= max_items` (else `ValidationError`).
3. Assemble `question_ids`; if empty/short, raise.
4. `deadline_at = started_at + duration_minutes`. Build `config = {count, question_ids: [str...], deadline_at, max_score, passing_score, duration_minutes}`.
5. Create `ExamSession(user_id, organization_id, blueprint_id, session_kind=fixed, status=in_progress, total_questions=len(question_ids), config=...)`. `log_audit(edit, entity_type="exam_session")`. Return it.

**Lazy auto-submit** — `_auto_submit_if_expired(session, ps) -> bool`: if `ps.status == in_progress` and `now >= config.deadline_at`, set `status=auto_submitted`, `ended_at=deadline_at`, flush, return True. Called at the top of every interactive service function.

**Load + own** — `_load_session(session, session_id, user_id)`: by id; `NotFound` if missing or `user_id` mismatch.

**Question delivery** — `get_question_at(session, *, session_id, position, user_id) -> dict`:
- `_auto_submit_if_expired`; if not `in_progress`, `ConflictError` (exam ended).
- Validate `0 <= position < len(question_ids)` else `ValidationError`.
- Load question + options (no `is_correct` leaked — same stripping as practice).
- Return `{session_id, position, total, question_id, stem, question_type, options[no is_correct], elapsed_ms, time_remaining_ms, previous_answer}`. `previous_answer` = the stored `selected` for this question if the learner already answered it (supports revising), else `None`.

**Answer submission (revisable)** — `submit_answer(session, *, session_id, user_id, payload: ExamAnswerIn) -> dict`:
- `_auto_submit_if_expired`; if not `in_progress`, `ConflictError`.
- Validate position; load question + options; build snapshot; judge from snapshot (compute `is_correct` but do **not** return it).
- Upsert `ExamAnswer` for `(session_id, question_id)`: if a row exists, overwrite `question_snapshot`/`options_snapshot`/`user_answer`/`is_correct`/`time_spent_ms`/`answered_at`; else insert. (Re-answer revises the previous answer.)
- `time_spent_ms` = `now - payload.started_at` (clamped ≥ 0), as in practice.
- `log_audit(edit, entity_type="exam_answer")`.
- Return `{position, saved: true, time_remaining_ms}` — no judgment.

**Finish** — `finish_session(session, *, session_id, user_id) -> ExamReportOut`:
- `_auto_submit_if_expired`.
- If `status == in_progress`: set `status = completed` (manual finish), `ended_at = now`. (If auto-submitted, leave `auto_submitted`.)
- Recompute `ps.correct_count` = count of `ExamAnswer.is_correct == True` for this session (handles revisions).
- `log_audit(edit, entity_type="exam_session", details={finished: True, auto: bool})`.
- Build + return the report (see below).

**Report** — `_build_report(session, ps) -> ExamReportOut`:
- `answers` = all `ExamAnswer` rows for the session.
- `correct = sum(is_correct)`; `answered = len(answers)`.
- `max_score`/`passing_score` from `config` (historical basis).
- `scaled_score = round(correct / total_questions * max_score)` (total_questions, not answered — unanswered count as wrong).
- `passed = scaled_score >= passing_score`.
- `accuracy = correct / total_questions`.
- `total_time_ms = sum(time_spent_ms)`; `avg_time_ms = total_time_ms / answered` (0 if none).
- Per-domain: for each answer, resolve its `QuestionMapping.domain_id`; group → `{domain_id, domain_name, weight_pct, answered, correct, accuracy}`.
- `wrong_questions = [{question_id, stem (from snapshot), selected_indexes, correct_indexes}]` for `is_correct == False` (and unanswered? no — unanswered are simply absent from `answers`; they are not "wrong questions", they are missed. The report includes `answered` vs `total_questions` so missed count is visible).
- Returns `{session_id, status, total_questions, answered_count, correct_count, scaled_score, max_score, passing_score, passed, accuracy, total_time_ms, avg_time_ms, domains[], wrong_questions[]}`.

**Unified review** — `get_review(session, *, session_id, user_id) -> list[ReviewItemOut]`:
- Only when `status in (completed, auto_submitted)` else `ConflictError("exam not finished")`.
- For each `question_id` in `config.question_ids` (in order): load live question+options+`Explanation` + the learner's `ExamAnswer` (if any). Return `{position, question_id, stem, question_type, options[with is_correct + per-option explanation], correct_rationale, key_point_summary, your_answer: {selected, is_correct} | None, time_spent_ms}`. Reads correctness from the **stored snapshot** (NFR-DATA-01) for `your_answer.is_correct`; per-option `is_correct` in review also reads from the snapshot so a later edit does not change what was graded.

**History + trend** — `list_history(session, *, user_id) -> list[ExamHistoryItemOut]`:
- Select `ExamSession` for user where `status in (completed, auto_submitted)`, tenant-scoped, ordered by `started_at asc`.
- For each: compute `scaled_score`/`passed`/`accuracy` from `config` basis + `correct_count`/`total_questions`. Return `{id, started_at, ended_at, status, total_questions, correct_count, scaled_score, max_score, passed, accuracy}`. The trend is the client plotting `scaled_score` over `started_at`.

## Schemas (`app/schemas/exam.py`)

- `ExamCreateIn`: `count: int | None = None` (optional; validated against blueprint bounds in service).
- `OptionDelivery` / `QuestionDeliveryOut` (no `is_correct`): `{session_id, position, total, question_id, stem, question_type, options, elapsed_ms, time_remaining_ms, previous_answer}`.
- `ExamAnswerIn`: `{position: int >= 0, selected: list[int], started_at: datetime}`.
- `ExamAnswerAck`: `{position, saved: bool, time_remaining_ms}`.
- `ExamSessionOut`: `{id, status, session_kind, total_questions, correct_count, started_at, ended_at, time_remaining_ms, config}` (`time_remaining_ms` computed; `config.question_ids` omitted from the HTTP response to avoid leaking the full set).
- `DomainPerformance`: `{domain_id, domain_name, weight_pct, answered, correct, accuracy}`.
- `WrongQuestion`: `{question_id, stem, selected_indexes, correct_indexes}`.
- `ExamReportOut`: as above.
- `ReviewOption` (with `is_correct` + `explanation`), `ReviewItemOut`, `ExamHistoryItemOut` as above.

## HTTP API (`app/api/exam.py`)

All routes gated by `require_permission("exam:read")` (exists in seed, granted to `individual_learner`). Error mapping: `NotFound`→404, `ValidationError`→422, `ConflictError`→409. Caller commits after successful mutations.

| Method | Path | Handler | Returns |
|---|---|---|---|
| POST | `/api/exam/sessions` | `create_exam` | `ExamSessionOut` |
| GET | `/api/exam/sessions/{id}` | `get_exam_detail` | `ExamSessionOut` |
| GET | `/api/exam/sessions/{id}/questions/{position}` | `get_exam_question` | `QuestionDeliveryOut` |
| POST | `/api/exam/sessions/{id}/answers` | `submit_exam_answer` | `ExamAnswerAck` |
| POST | `/api/exam/sessions/{id}/finish` | `finish_exam` | `ExamReportOut` |
| GET | `/api/exam/sessions/{id}/report` | `get_exam_report` | `ExamReportOut` |
| GET | `/api/exam/sessions/{id}/review` | `get_exam_review` | `list[ReviewItemOut]` |
| GET | `/api/exam/history` | `list_exam_history` | `list[ExamHistoryItemOut]` |

Router registered in `app/main.py` after `practice_router`. Handler names avoid shadowing `get_session` (lesson from E: the detail handler is `get_exam_detail`, not `get_session`).

## Error handling

- No current blueprint → 422 `ValidationError`.
- Count outside `[min_items, max_items]` → 422.
- Not enough published questions to assemble → 422.
- Position out of range → 422.
- Interacting with a non-`in_progress` session (finished/auto-submitted/aborted) for deliver/answer → 409 `ConflictError`.
- Review before finish → 409.
- Other user's session → 404 (no leak that it exists).

## Testing

Service tests (`tests/test_exam_service.py`) and HTTP tests (`tests/test_exam_api.py`) against the `cissp_test` DB, mirroring the practice test harness. Coverage:
- Assembly: domain weights sum to count (largest-remainder); short domain triggers redistribution; overall shortage → `ValidationError`; no current blueprint → `ValidationError`; count clamping.
- Delivery strips `is_correct`; returns `time_remaining_ms`; `previous_answer` after a prior submit.
- Answer: revisable (second submit overwrites, one `ExamAnswer` row); `is_correct` not returned; snapshot persisted.
- Lazy auto-submit: after deadline, deliver/answer/finish transitions `status=auto_submitted`.
- Finish: recomputes `correct_count` from answers; scaled score + pass math; per-domain grouping; wrong-question list.
- Review: only after finish; reads correctness from snapshot (edit a question's options after answering → review still shows the original correct answer).
- History: ordered by `started_at`; only completed/auto-submitted; historical scoring basis from `config` (edit blueprint's `passing_score` → past exam's `passed` unchanged).
- Tenant isolation: another user's session → 404.
- Migration drift test stays green (the new `config` column is covered by the migration).

## Acceptance

Sub-project F is done when: a learner can create a fixed exam from the current blueprint, answer under timing with no feedback, auto-submit on timeout, and receive a correct report + unified review + history — all from snapshots — with the full backend suite passing and zero migration drift.
