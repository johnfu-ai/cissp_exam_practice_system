# Plan: Paper banks, resume, mode switch, player UX fixes (PRD v1.5)

Spec: `docs/superpowers/specs/2026-09-25-paper-banks-resume-mode-switch-design.md`

TDD throughout — tests land in the same commit as the code they cover.

## 1. Backend

1. `tests/test_paper_banks_resume.py` (red):
   - `GET /api/banks` — published counts only, `has_papers`, excludes empty datasets.
   - `dataset_slug` scoping in `POST /api/practice/sessions`.
   - heartbeat: monotonic + clamp(Δ ≤ 300 s), 409 when not in progress;
     `elapsed_ms` in delivery counts the active window (≤120 s grace) and
     excludes away time; legacy sessions fall back to wall clock.
   - `GET /api/papers/sessions/{id}/state` — practice (answered/wrong/elapsed),
     exam (deadline, `wrong_positions=[]`), bank practice (paper_id null), 404
     cross-user.
   - `GET /api/papers/sessions/in-progress` — paper + bank sessions, newest
     first, finished excluded.
   - `POST /api/papers/sessions/{id}/switch-mode` — p→e (copy + deadline from
     remaining + old abandoned + 422 when exhausted), e→p (copy + judge +
     record_outcome + correct_count + elapsed seed + old aborted), idempotent
     same-kind, 404/409/422 paths, audit rows.
   - `previous_answer.text` for practice + exam essay delivery.
2. Implement (green):
   - `services/paper.py`: `list_banks`, `session_state`, `switch_mode`,
     `list_in_progress`, `_practice_elapsed_seconds` helper (shared import from
     practice service), score map helper.
   - `services/practice.py`: `dataset_slug` candidate filter,
     `heartbeat` service, elapsed-from-accumulated in `get_question_at`,
     `previous_answer.text`.
   - `services/exam.py`: `previous_answer.text`.
   - `api/papers.py`: 4 new routes; `api/practice.py`: heartbeat route;
     `schemas/practice.py`: `dataset_slug` + heartbeat models.
3. `pytest` full suite + zero migration drift (no model changes expected).

## 2. Contract

4. `python -m app.scripts.export_openapi ../openapi/openapi.json`; frontend
   `npm run gen:api`; hand-extend `lib/api/types.ts` (banks, resume state,
   in-progress, switch-mode) + `lib/api/keys.ts`.

## 3. Frontend (TDD)

5. `papers-view.test.tsx` (red): banks section renders (name/count), count
   select + order buttons POST `/api/practice/sessions` with `dataset_slug`,
   route without `paper` param; in-progress section renders continue links.
   Implement `papers-view.tsx` + `lib/api/papers.ts` hooks + locales (en/zh).
6. `player.test.tsx` (red):
   - sheet keeps its size while the next question loads (`total` stable);
   - palette wrapper is the scrollable region (`overflow-y-auto` + max height);
   - resume state seeds sheet/timer base/first-unanswered position;
   - heartbeat fires on an interval (fake timers) with `elapsed_seconds`;
   - mode switch button POSTs and `router.replace`s to the returned session,
     hidden without a paper, error text on failure;
   - practice essay re-hydrates `previous_answer.text`.
   Implement `player.tsx` (+ small `resume` helpers in `answer-sheet.ts` if
   pure) + locales.
7. `npm run test && npm run lint && npm run build` — all green.

## 4. End-to-end verification

8. Rebuild the stack (`docker compose up -d --build`); live smoke: `/api/banks`
   shows osg10; bank practice session; exit + resume keeps answers/elapsed;
   mode switch both directions on a real paper; palette scroll + no flash
   (manual browser check).
9. Playwright: existing suites still green; extend `paper-practice` spec with a
   resume step if stable (keep CI-friendly).

## 5. Wrap-up

10. Update `CLAUDE.md` (current state + API notes), append `ai-log.md`, commit
    per logical unit (docs → backend → contract → frontend → e2e/docs).
