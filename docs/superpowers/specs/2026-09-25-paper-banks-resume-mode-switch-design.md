# Design: Paper banks, resume, mode switch, player UX fixes (PRD v1.5)

Date: 2026-09-25
PRD: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` §6.14 FR-PAPER-10..13 (v1.5)
Plan: `docs/superpowers/plans/2026-09-25-paper-banks-resume-mode-switch.md`

## Problem statements (from user report)

1. **OSG v10 bank unreachable** — since the v1.4 learner flow lands on `/papers`,
   which lists only `Paper` rows, the osg10 dataset (320 published questions, 0
   papers) has no learner entry point.
2. **"结束练习" button flash** — clicking a not-yet-cached question number makes
   `q` undefined while the delivery loads, so `total` collapses to 0, the
   answer-sheet grid unmounts, the left card shrinks, and the finish button
   jumps into view then back down. Cached positions return instantly → no flash.
3. **Answer palette too long** — papers with 100+ questions render a ~17-row
   grid with no height bound; timer/legend/submit button end up below the fold.
4. **No practice⇄exam mode switch** — FR-PAPER-05 promises 模式切换 in the
   player info area; never implemented.
5. **No re-entry (resume)** — answers persist server-side, but: the papers page
   always creates a NEW session (no continue entry); practice elapsed time is
   client-only (`Date.now()` at mount); essay `previous_answer` carries no
   saved text (practice and exam delivery both return `selected` only).

## Design

### A. Free-practice banks (FR-PAPER-10)

- `GET /api/banks` (`practice:read`, papers router): one row per org dataset
  (`EtlDataset` joined to published-question counts via `QuestionExternalKey`)
  with ≥1 published, non-deleted question: `{dataset_slug, name, question_count,
  languages, has_papers}`. `has_papers` = published `Paper` rows exist for the
  slug → the UI shows paper cards for those and free-practice cards for the rest.
- `SessionCreateIn.dataset_slug` (optional): `_candidate_question_ids` adds an
  `Question.id IN (SELECT question_id FROM question_external_keys WHERE
  dataset_slug = …)` filter. Everything else (subset/order/count/language)
  reuses the existing practice machinery.
- `/papers` renders a “自由练习题库” section: dataset card + count selector
  (10/20/50/100/200, default 20 — the API caps `count ≤ 200`) + 顺序练习 /
  随机练习 buttons → `POST /api/practice/sessions {dataset_slug, count,
  order_mode}` → route `/paper-play/{id}?kind=practice` (no `paper` param).

### B. Resume bundle + heartbeat (FR-PAPER-12)

- `GET /api/papers/sessions/{session_id}/state` (`practice:read`, owner-scoped,
  404 otherwise). Accepts a `PracticeSession` or `ExamSession` (paper or bank):
  `{session_id, kind, status, paper_id, paper_name, total, answered_positions,
  wrong_positions, elapsed_seconds, deadline_at}`.
  - practice: `answered_positions` from `PracticeAnswer` rows (position =
    index in `config.question_ids`), `wrong_positions` = judged false
    (exam-mode sheets never expose correctness → `[]` for exams);
    `elapsed_seconds` = accumulated heartbeat time (see below).
  - exam: `deadline_at` from config (server-authoritative; lazy auto-submit on
    delivery already exists).
- `POST /api/practice/sessions/{id}/heartbeat {elapsed_seconds}` → stores
  `config.elapsed_seconds = clamp(max(prev, client), prev + 300)` and
  `config.last_seen_at = now` (`flag_modified` for JSONB). 409 unless in
  progress. The clamp bounds a single jump to 5 min (anti-runaway), monotonic.
- Practice elapsed resolution (`_practice_elapsed_seconds`):
  - `base = config.elapsed_seconds or 0`
  - if `last_seen_at` within 120 s grace → `base + (now − last_seen)` (active
    window), else `base` (away time not counted)
  - no `last_seen_at` at all (legacy / non-heartbeating clients) → wall clock
    `now − started_at` (old behavior preserved).
  `get_question_at.elapsed_ms` uses this for all practice sessions.
- Delivery `previous_answer` gains `text` (practice + exam): essay answers
  re-hydrate their saved free text on re-entry.
- `GET /api/papers/sessions/in-progress`: the caller's in-progress sessions
  that belong to papers (`config.paper_id`) or banks
  (`config.dataset_slug`), newest first:
  `{session_id, kind, source: paper|bank, paper_id?, paper_name?,
  dataset_slug?, dataset_name?, total, answered, started_at}`.
- Player mounts → fetch state → seed the answer sheet (answered/wrong), set
  `startedEpoch = now − elapsed_seconds·1000` (practice) or deadline (exam,
  replaces the ad-hoc config fetch), and jump to the first unanswered position.
  Heartbeat fires every 20 s while a practice session is in progress.

### C. Mode switch (FR-PAPER-11)

- `POST /api/papers/sessions/{session_id}/switch-mode {mode}` (papers router,
  owner-scoped). Same-kind requests are idempotent no-ops returning the same id.
- **practice → exam**: new `ExamSession` (kind fixed, `scoring=paper`) over the
  SAME `question_ids` order from the practice config; per-question scores from
  the current paper (by question_id); `deadline = now + max(0, duration·60 −
  elapsed_seconds)`; `elapsed ≥ duration` → 422. Copies every `PracticeAnswer`
  into `ExamAnswer` (snapshot, options snapshot, user_answer, is_correct incl.
  essay self-assessments, time_spent_ms). Old `PracticeSession` → `abandoned`.
- **exam → practice**: new `PracticeSession` (paper config + sequential order
  from the exam config) with `config.elapsed_seconds` seeded from the exam's
  wall-clock elapsed; copies every `ExamAnswer` into `PracticeAnswer`, judging
  choice answers from their snapshots (essay stays `None` until self-assessed),
  sets `correct_count`, and feeds each judged copy through
  `wrong_book.record_outcome` (same as a normal practice submit; the old exam
  never finishes, so there is no double count from that side). Old
  `ExamSession` → `aborted`.
  - Wrong-book double counting on practice→exam finish is ACCEPTED by design:
    every judged outcome counts (re-practice already accumulates `wrong_count`
    per answer, FR-WRONG-05).
- Both directions audit (`entity_type` = the new session, details carry
  `switched_from`). Response `{session_id, kind, paper_id}` → the player
  `router.replace`s to the new session.

### D. Player UX (FR-PAPER-13 + flash fix)

- `stableTotal` state: set once per loaded question (`q.total`), never reset to
  0 while loading → the sheet, counts, and next-button bounds stay mounted; the
  main column still shows `<Loading>` between questions.
- The palette grid wrapper gets `max-h-[50vh] overflow-y-auto` so the info card
  (timer + legend + finish button) stays in view for any paper length.
- Mode-switch button lives in the left card under the mode badge; only for
  paper sessions in progress (bank sessions hide it). Switch errors (e.g. time
  exhausted) render inline under the button.

### Non-goals / follow-ups

- Miniprogram adoption of banks/resume/switch endpoints (contract is shared;
  delivery changes are backward compatible — old clients keep working).
- Multi-device concurrent play locking.

## Test strategy

- Backend (new `tests/test_paper_banks_resume.py` + additions): banks listing &
  gating; dataset-scoped practice; heartbeat clamp/monotonic + elapsed grace +
  away-time exclusion; resume state (practice/exam/bank, 404s, wrong positions
  suppressed for exam); in-progress listing filters; switch-mode round trips
  both directions + all error paths + audit rows; `previous_answer.text` for
  practice and exam essays.
- Frontend (vitest): papers-view renders banks + resume entries and posts the
  right payloads; player — sheet does not collapse while loading, palette is
  scrollable, resume state seeds sheet/timer/position, heartbeat interval calls
  the endpoint, mode switch calls and routes, essay text re-hydrates.
- Full suites: backend pytest (incl. migrations zero-drift), frontend
  vitest/lint/build, openapi re-export + `gen:api`, Playwright e2e against the
  rebuilt stack, plus a live curl smoke of the new endpoints.
