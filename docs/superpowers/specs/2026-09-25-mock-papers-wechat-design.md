# Design: Paper Papers, Essay Questions, Wrong Book, WeChat Mini Program (PRD v1.4)

Date: 2026-09-25
Status: Accepted
PRD: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` v1.4 (FR-PAPER, FR-ESSAY, FR-WRONG, FR-ETL-17..19, FR-CLIENT v1.4, NFR-TEST)

## 1. Backend

### 1.1 Question type: `essay`

- Add `essay` to `QuestionType` (native PG enum — migration `ALTER TYPE ... ADD VALUE`).
- `QuestionTranslation.reference_answer: Text | NULL` (per language). Essay questions have **zero** `QuestionOption` rows; the answer key is the reference answer.
- Validation (`app/services/question.py::_validate_options`): `essay` → 0 options allowed, at least one language's `reference_answer` non-empty required for publish.
- Snapshot (`app/services/snapshot.py`): include `reference_answer` in per-language translations block.
- Judging: essay answers are **never auto-judged**. `_judge` returns `None` for essays (no `is_correct` indexes). `user_answer` payload for essay = `{"text": "..."}`.
- Practice flow (FR-ESSAY-02): `POST /api/practice/sessions/{id}/questions/{pos}/answer` with `{"answer_text": "..."}` records the answer, `is_correct=NULL`, returns reference answer (Localized) in the result; then `POST .../self-assessment {"correct": bool}` updates `PracticeAnswer.is_correct`, mastery, and wrong book.
- Exam flow (FR-ESSAY-03): exam answer submit accepts `answer_text`; no reference shown while active; after finish, `POST /api/exam/sessions/{id}/answers/{pos}/self-assessment {"correct": bool}` updates `ExamAnswer.is_correct` + wrong book + report recompute (report is derived on read — no stored score to invalidate except scaled fields computed in `_build_report`).
- CAT candidate pool excludes `essay` (as it already excludes non-published; add explicit type filter).

### 1.2 Papers (FR-PAPER)

New models (`app/models/paper.py`):

- `Paper`: `id` UUID PK, `organization_id` (tenant), `name` Text, `description` Text NULL, `duration_minutes` Int NULL, `total_score` Numeric/Int, `question_count` Int, `status` Enum(paper_status: draft|published|archived) default published, `dataset_slug` String NULL, `paper_external_id` String NULL, unique `(dataset_slug, paper_external_id)` (nullable-safe for manual papers), `domain_number` Int NULL, timestamps + soft delete.
- `PaperQuestion`: `paper_id` FK, `question_id` FK, `position` Int, `score` Numeric default 1, unique `(paper_id, position)`.

API (`app/api/papers.py`, permission `practice:read` for learner ops):

- `GET /api/papers` — published papers for the org (admin sees all via `?all=1` + `question:read`), each with `question_count/duration/total_score/domain` + caller's session history summary (attempts, best score).
- `GET /api/papers/{id}` — detail incl. per-type counts.
- `POST /api/papers/{id}/sessions` `{"mode": "practice"|"exam", "language_mode"?}` — practice mode creates `PracticeSession` with `config.question_ids = paper order`; exam mode creates `ExamSession` (kind `fixed`) with `config.paper_id`, `config.scoring="paper"`, `config.question_ids = paper order`, `duration_minutes`/`deadline_at` from paper, `max_score = total_score`, per-question `scores` list in config.
- `GET /api/papers/{id}/sessions` — caller's sessions on this paper.

Exam report branch: when `config.scoring == "paper"`, `_build_report` scores `sum(scores[i] for correct answers])`, pass line 60%, no scaled 1000 conversion, marks essay-unassessed as 0.

### 1.3 Wrong book (FR-WRONG)

- `UserQuestionState` += `wrong_count` Int default 0, `last_wrong_at` DateTime NULL (migration).
- Increment on judged-incorrect in: practice submit, exam finish (lazy judge), paper exam finish, self-assessment `correct=false`. Reset nothing on correct (count is cumulative); mastery flow: `is_mastered=true` moves question out of "我的错题" tab; re-practice correct promotes `mastery_level` (existing logic).
- `GET /api/wrong-book?tab=wrong|bookmarked|flagged&paper_id=` (`practice:read`): returns items `{question_id, snapshot summary (type/stem excerpt/options/answer/explanations), wrong_count, last_wrong_at, is_mastered, is_bookmarked, is_flagged_review, papers: [names]}`, ordered by `last_wrong_at desc`.
- `POST /api/wrong-book/practice {paper_id?, count?}` — creates practice session with `subset=wrong` (+ optional paper filter via join through `PaperQuestion`).

### 1.4 ETL (FR-ETL-17..19)

- `app/etl/paper_export.py` (pure + CLI): converts `paper_*.json` (+ optional `wrong_questions_*.json` ignored for MVP) → dataset dir `docs/questions/mockpapers/` with `manifest.json`, `questions.jsonl`, `papers.json`.
  - Bilingual split: stems by `<p>` blocks, else inline first-CJK-boundary; options strip `^[A-Z][.、]\s*` prefix then split; `answerAnalysis` per-option → `option_explanations`, correct-option analysis preferred as question explanation; Word-HTML normalization (strip `MsoNormal` classes, `&nbsp;` → space, drop `font-family` spans); external id `mockpapers-{paperIdx:02d}-{q.sort}`? No — question-level external id from paper `question.id`: `paper-{id}` (stable across papers, dedupes naturally).
  - Book/chapter: book `CISSP 模拟试卷`, edition 1, chapter = paper index 1..8, chapter_title = paperName; `domain_number` = paper index (papers 一..八 map to CISSP domains 1..8).
  - `papers.json` rows: `{id, name, duration_minutes, domain_number, question_ids: [paper-<qid>...], scores: [q.score...], total_score, status: "published"}`.
- Transform: `essay` type — no options/correct_keys required; `reference_answer {en,zh}` validated non-empty in ≥1 language.
- Load: after questions, process `papers.json` idempotently (`(dataset_slug, paper_external_id)`): upsert Paper + replace PaperQuestion rows; question refs resolved via `QuestionExternalKey`; missing refs → whole paper to error report, skipped.
- Seed registers `mockpapers` dataset (directory present in repo) — actual import still runs via two-phase ETL API.

### 1.5 Migrations

One migration: `essay` enum value (ALTER TYPE ADD VALUE, apply before table DDL), `question_translations.reference_answer`, `user_question_states.wrong_count/last_wrong_at`, `paper_status` enum + `papers`/`paper_questions` tables + unique indexes. Drift test stays zero (run autogenerate and reconcile).

## 2. Web learner (Next.js)

- Restore deleted learner infrastructure only where needed; new-first approach for paper flow:
  - `/papers` — paper list (题库): cards with name, counts, duration, score, domain badge, my attempts; buttons 开始练习/开始考试.
  - `/papers/[id]` — paper player (paper style): header (title, duration/score, timer), left column answer sheet grid (已答/错误/未答/标记) + counts + mode + submit; main area question (type badge, 纠错/标记/收藏 actions, bilingual toggle, options / essay textarea, prev/next). Practice mode: per-question immediate feedback panel (correct answer, per-option explanations, reference answer + self-assess buttons for essay). Exam mode: palette nav, revisable answers, countdown + submit → redirect report.
  - `/papers/[id]/sessions/[sessionId]` — report/review (fixed-exam style report branched for paper scoring; per-question review incl. essay reference + self-assessment).
  - `/wrong-book` — tabs 我的错题/我的收藏/我的纠错, paper filter, cards with actions (重新练习/查看解析/我已掌握).
- `require-auth` gating: learner routes allowed for all authed users; root page redirects learners → `/papers`; sidebar gains learner section (题库/错题集) visible to all, manage section stays permission-gated.
- i18n: all new chrome through `t()`; add keys to both `en.ts`/`zh.ts`.
- Tests: vitest unit tests for new helpers/components (answer-sheet state, paper player invariants: language toggle never advances/submits); Playwright e2e (see §4).

## 3. WeChat mini program (`miniprogram/`)

Native (no framework). Structure:

```
miniprogram/
├── project.config.json, app.{js,json,wxss}
├── lib/           # pure CommonJS, vitest-tested
│   ├── config.js  # API base (env switch)
│   ├── request.js # wx.request promise wrapper + auth + 401 refresh (body refresh_token)
│   ├── auth.js    # token storage, login/logout
│   ├── i18n.js    # en/zh dicts + t()
│   ├── papers.js  # paper API calls
│   ├── session.js # answer-sheet state machine, timer helpers, submit logic
│   └── wrong-book.js
├── pages/
│   ├── login/     # login + register
│   ├── papers/    # paper list (题库)
│   ├── play/      # paper player (practice/exam modes)
│   ├── report/    # session report/review (essay self-assessment)
│   ├── wrong/     # wrong book (3 tabs)
│   └── settings/  # interface language, content language, change password
├── components/    # question-view, option-list, answer-sheet, rich-text renderer
└── tests/         # vitest (mock global wx)
```

- Auth: username/password → JWT access (memory + storage) + refresh token parsed from `Set-Cookie` header stored in wx storage; 401 → single-flight refresh via body.
- API base: `lib/config.js` reads `wx.getAccountInfoSync().miniProgram.envVersion` or a config page; dev default `http://localhost:8000` (devtools doesn't enforce domain whitelist with "不校验合法域名" checked).
- rich-text: use `<rich-text>` with backend-sanitized HTML.

## 4. E2E & tests (NFR-TEST)

- Backend: TDD — every backend change lands with tests first (pytest, real Postgres). New suites: `test_paper_export_converter.py` (golden tests over the real exports), `test_essay_*.py`, `test_paper_*.py`, `test_wrong_book_*.py`, ETL papers load tests in `tests/etl/`.
- Web Playwright (`frontend/e2e/`, config `frontend/playwright.config.ts`, devDependency `@playwright/test`): journeys `auth`, `paper-practice` (login → papers → practice → answer → submit → wrong book → master), `paper-exam` (timed exam → submit → report → review essay self-assess). `webServer`s: backend uvicorn (against docker/CI postgres+redis) + frontend `next start`. npm scripts: `e2e`, `e2e:install`.
- Mini program: `miniprogram/package.json` with vitest; `tests/` cover request wrapper (mock wx.request), refresh single-flight, answer-sheet state machine, i18n parity, timer formatting.
- CI: replace 4 mobile jobs with `miniprogram` job (npm ci + vitest); add `e2e-web` job (services postgres+redis + backend + frontend + playwright chromium); release.yml drops android/windows/ios jobs.

## 5. Removal of Flutter

- `git rm -r mobile/` (history preserved); remove mobile jobs from ci.yml/release.yml; delete `scripts/check_dart_api_drift.sh`; clean `.gitignore` mobile block; update READMEs, `frontend/README.md`, `app-sidebar.tsx` comment, CLAUDE.md, production runbook Android keystore section.

## 6. Risks / decisions

- Exam essay scoring: unscored (0) until self-assessed — report recomputes on read; `GET report` reflects latest self-assessments.
- `ExamSessionKind` stays `fixed` for paper exams; paper branch keyed on `config.paper_id` (avoids enum migration + branch sprawl).
- paper images in explanations are external URLs; nh3 sanitization keeps `img` tags with https src (extend allowlist) — external hosting availability is acceptable (source data as-is).
- Mini program e2e automation (miniprogram-automator) needs Windows/macOS devtools — out of CI scope, documented as manual acceptance.
