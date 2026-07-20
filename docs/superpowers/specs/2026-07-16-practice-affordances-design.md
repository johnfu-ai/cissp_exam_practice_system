# Practice affordances: timer / shuffle / notes / same-KP (#36-rem)

**Date:** 2026-07-16
**Audit item:** Frontend P1 #36-rem (FR-PRAC-09, FR-ANS-01, FR-ANS-07, FR-ANS-08, §8.1).
**Branch:** `feat/p3-practice-affordances`

## Problem

The practice runner tracks `elapsed_ms` server-side but never displays a timer; option shuffling (§8.1 config) is absent; the notes dialog opens empty (no view/edit of an existing note); and same-knowledge-point recommendation (FR-ANS-08) is missing.

## Design

### Backend (`app/schemas/practice.py`, `app/services/practice.py`, `app/api/practice.py`)

1. **Timer** - already supported (`QuestionDeliveryOut.elapsed_ms`, `AnswerIn.started_at`). Frontend-only display work.
2. **Option shuffle** - `SessionCreateIn.shuffle_options: bool = False`; stored in `config["shuffle_options"]`. The backend still returns canonical `order_index`; the frontend shuffles DISPLAY only (selection stays canonical `order_index`, so judging is unaffected). No backend delivery change.
3. **Notes view/edit (FR-ANS-07)** - `QuestionDeliveryOut.note: str | None = None`; `get_question_at` reads the current `UserQuestionState.note` for `(user, question)` so the dialog can pre-load.
4. **Same-KP recommendation (FR-ANS-08)** - `GET /api/practice/questions/{question_id}/related` -> up to 5 live questions sharing a knowledge-point with the given question (same org, not deleted, not mastered by the user, excluding the current question), each `{question_id, stem:{en,zh}, knowledge_point_id}`. Service `related_questions(session, *, user_id, org_id, question_id)`. Gated by `practice:read`.

### Frontend (`features/practice/`)

1. **Timer** - runner shows a live session timer (from `session.started_at`) + per-question timer (from the runner's `startedAt`); a 1s `setInterval` tick; paused while `paused_at` set; per-question time shown on the result panel.
2. **Shuffle** - create-session-form gains a `shuffle_options` checkbox; the runner reads `session.config.shuffle_options` and applies a deterministic (question_id-seeded) display permutation to `OptionList` options. Selection/submit stay canonical `order_index`.
3. **Notes** - `NoteDialog` initializes from `delivery.note`.
4. **Same-KP** - after submit, fetch `/api/practice/questions/{id}/related` and render a "Related practice" panel with a re-practice launcher.

## Tests

- Backend: delivery carries `note`; `shuffle_options` persists into config; `related` returns same-KP non-mastered questions (excluding current), org-scoped, 404 on missing question, empty list when no KP.
- Frontend: runner renders a timer; NoteDialog pre-loads the existing note; shuffle permutation is deterministic + selection stays canonical (existing cat-runner-style invariant test).

## Out of scope

- A separate `POST /api/questions/{id}/notes` CRUD resource (PRD §9.5) - the existing `UserQuestionState.note` field + `PUT /state` already satisfy FR-ANS-07's "add a personal note" intent; surfacing it on delivery closes the view/edit gap without a new table.
