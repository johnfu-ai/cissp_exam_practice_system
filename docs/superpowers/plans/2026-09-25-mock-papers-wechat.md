# Plan: MockPaper Papers, Essay, Wrong Book, WeChat Mini Program (PRD v1.4)

TDD throughout — tests land before/with each step. Each numbered step ends runnable & green.

## Wave 1 — Docs (done first)

1. [x] PRD v1.4 (FR-PAPER/FR-ESSAY/FR-WRONG/FR-ETL-17..19/FR-CLIENT/NFR-TEST, §7.6, §8, §9, §10, §12, §13, §14, §15, §17, §18).
2. [x] Design spec `docs/superpowers/specs/2026-09-25-paper-papers-wechat-design.md`.
3. [x] This plan.

## Wave 2 — Backend (TDD)

4. MockPaper converter `app/etl/paper_export.py`: tests over real exports (bilingual split, letter-prefix strip, Word-HTML normalize, analysis merge, papers.json emission, idempotent re-run) → implementation → generate `docs/questions/mockpapers/`.
5. Models + migration: `essay` enum, `QuestionTranslation.reference_answer`, `UserQuestionState.wrong_count/last_wrong_at`, `PaperStatus` enum, `Paper`/`PaperQuestion`; model tests; `alembic revision --autogenerate` + zero-drift check.
6. Essay question lifecycle: `_validate_options` essay rules, editor schemas (reference_answer), publish completeness, translation delivery/snapshot reference_answer. Tests: `test_question_essay.py`.
7. Essay answering: practice answer `answer_text` + result reference answer; practice self-assessment endpoint; exam answer `answer_text`; exam post-finish self-assessment endpoint; judge returns None for essay; CAT pool excludes essay. Tests: `test_practice_essay.py`, `test_exam_essay.py`.
8. Wrong book: `wrong_count`/`last_wrong_at` increments in practice submit + exam finish; `GET /api/wrong-book` (+tabs+paper filter); `POST /api/wrong-book/practice`. Tests: `test_wrong_book.py`.
9. Papers API: `GET /api/papers`, `GET /api/papers/{id}`, `POST /api/papers/{id}/sessions` (practice/exam), `GET /api/papers/{id}/sessions`; paper-scoped exam report scoring. Tests: `test_paper_api.py`, `test_paper_exam_report.py`.
10. ETL: transform essay validation; extract `papers.json`; load Paper/PaperQuestion idempotent + error isolation; runner preview counts include papers; seed registers `mockpapers`. Tests: `tests/etl/test_papers_load.py`, extend converter/preview tests.
11. openapi re-export + full backend suite green (incl. migration drift test).

## Wave 3 — Web learner

12. Learner gating: root redirect + require-auth learner routes + sidebar learner section + i18n keys.
13. `/papers` list page + tests.
14. `/papers/[id]` player (practice + exam modes, answer sheet, timer, essay textarea, feedback panel, essay self-assessment) + tests (state machine, invariants).
15. Session report/review page (paper scoring branch, essay review self-assessment) + tests.
16. `/wrong-book` (3 tabs, filter, actions) + tests.
17. Playwright: config + journeys (auth, paper-practice, paper-exam incl. essay self-assess, wrong-book). Green locally against dev stack.
18. `npm run gen:api` types; lint/build/vitest green.

## Wave 4 — Mini program

19. Scaffold `miniprogram/` (project.config.json, app.*, tabbar, theme), lib/ + tests (request/refresh, i18n, answer-sheet, timer).
20. Pages: login → papers → play (practice/exam) → report (self-assess) → wrong → settings; components (option list, answer sheet, rich text).
21. vitest suite green; devtools manual smoke documented in README.

## Wave 5 — Removal + CI + release

22. Remove `mobile/`, mobile CI/release jobs, dart drift script, .gitignore block, doc references.
23. CI: `miniprogram` job, `e2e-web` playwright job; release.yml app jobs removed (release job artifact list fixed).

## Wave 6 — Verification & docs

24. Full stack e2e: compose up, migrate, ETL commit mockpapers (8 papers/828 questions), run scripts/e2e_smoke.sh + Playwright + backend/frontend/miniprogram suites.
25. CLAUDE.md, READMEs, production runbook updates; ai-log entry; final commit series.
