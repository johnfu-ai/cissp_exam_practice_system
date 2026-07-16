# Plan: ETL difficulty + per-option explanations + license (#16, #18)

**Spec:** `docs/superpowers/specs/2026-07-16-etl-difficulty-option-explanations-design.md`
**Branch:** `feat/p3-etl-difficulty-option-explanations`

## Steps (executed)

1. **extract.py** - `RawQuestion` gained optional `difficulty`, `option_explanations`, `license_status`. Added `_parse_difficulty` (int/numeric-string/label, clamp 1–5, garbage->None), `_parse_option_explanations` (split `option_explanations`+`option_explanations_zh` OR nested `{key:{en,zh}}`), and license passthrough. `_parse_record` wires them (top-level OR `meta.*`).
2. **transform.py** - `_resolve_difficulty(raw)`: source wins, else coarse type-based prior (`multiple_choice->4`, `true_false->2`, else `3`), else `DIFFICULTY_DEFAULT`. `CleanedOption` gained `explanation_en/explanation_zh` (default `""`); `CleanedQuestion` gained `license_status` (default None). `transform` populates both.
3. **load.py** - `_translation_payload` now returns `(stem, rationale, [(content, explanation), ...])`; `_write_translations` writes per-option `explanation` (empty->None for backward compat). `_resolve_license(cleaned)` honors source `license_status` (default unconfirmed). `_differs` now compares difficulty, license_status, and per-option explanations. `_apply_one` sets `q.license_status` on both create and update.
4. **Tests** - 27 new ETL tests (extract parse, transform resolve/carry, load write/detect/honor). All 552 backend tests pass; zero migration drift.

## Verification

- `pytest tests/etl/` -> 94 passed.
- `pytest` -> 552 passed (+27 from 525 baseline).
- `pytest tests/test_migrations.py` -> drift guard green (no model changes).

## Artifacts updated

- `docs/audits/2026-07-04-improvement-progress-and-roadmap.md` - #16, #18 -> DONE.
- `CLAUDE.md` "Current State" - new entry.
- Memory: [[cissp-improvement-audit]].
