# ETL: read difficulty + per-option explanations + license from source (#16, #18)

**Date:** 2026-07-16
**Audit items:** Tier 3 #16 (CAT difficulty from ETL) + #18 (per-option explanations + read difficulty/license from source).
**Branch:** `feat/p3-etl-difficulty-option-explanations`

## Problem

The ETL pipeline hardcodes three enrichment values regardless of source data:

1. **`difficulty=3`** for every question (`transform.py:116` → `DIFFICULTY_DEFAULT`). `RawQuestion` has no difficulty field, so even datasets that carry difficulty can't flow it through. With uniform difficulty, the CAT engine's ability-matched selection (§11.1 items 1+4, FR-CAT-05) is effectively meaningless.
2. **Per-option `explanation=None`** (`load.py::_write_translations` writes `"explanation": None`). The data model (`QuestionTranslation.options[].explanation` JSONB) and the question editor already support per-option explanations, and delivery already returns them as `{en, zh}` (`practice.py:408`, `exam.py:923/942`) — only ETL drops them. The PRD §10 import template lists `option_explanations` / `option_explanations_zh` (JSON keyed by option key).
3. **`license_status=unconfirmed`** hardcoded in `_apply_one` (`load.py:283`). FR-ETL-09 says license missing → `unconfirmed`, but a source-provided license status is ignored.

Additionally `_differs()` does **not** compare `difficulty`, so a difficulty enrichment never triggers an update on re-import.

## PRD basis

- FR-ETL-09: 难度缺失默认 medium；授权状态缺失默认 `unconfirmed`.
- §10 import template: `difficulty` (optional, default medium), `option_explanations` / `option_explanations_zh` (optional JSON per-option).
- §11.1: 每道题设置难度值，范围 1-5; FR-CAT-04/05 medium start + ability-matched next item.

The seeded osg10 dataset carries **none** of these fields, so for osg10 the behavior is unchanged (medium / no per-option explanation / unconfirmed) — but the pipeline becomes correct and ready for datasets that do carry them (e.g. the #35 CSV/XLSX upload with a `difficulty` column, or manual editor curation).

## Design

### extract.py — `RawQuestion` gains optional fields

- `difficulty: int | None = None` — parsed from `rec.get("difficulty")` (int 1–5, numeric string, or label) OR `rec.get("meta", {}).get("difficulty")`.
- `option_explanations: dict[str, Bilingual] | None = None` — merged from PRD-template fields `option_explanations` (en, `{key: text}`) + `option_explanations_zh` (zh, `{key: text}`), OR a single `{key: {en, zh}}` object. Keyed by option key.
- `license_status: str | None = None` — parsed from `rec.get("license_status")` or `meta.license_status`.

Add a `_parse_difficulty(value) -> int | None` helper (accepts int/str/label, clamps to 1–5, returns None on garbage/absent). Add `_parse_option_explanations(rec) -> dict[str, Bilingual] | None`.

### transform.py — resolve difficulty + carry per-option explanations

- New `_resolve_difficulty(raw) -> int`:
  - If `raw.difficulty` is a valid 1–5 → use it (source wins).
  - Else apply a **coarse type-based prior** (documented, overridable): `multiple_choice → 4`, `true_false → 2`, else (single_choice / matching→single / scenario) → 3. This gives the CAT pool real variation for the seeded data without inventing psychometric claims; the CAT `DISCLAIMER` already states it is a study tool, not official scoring.
  - `DIFFICULTY_DEFAULT = 3` stays as the final fallback.
- `CleanedOption` gains `explanation_en: str = ""`, `explanation_zh: str = ""`.
- `transform` populates `CleanedOption.explanation_en/zh` from `raw.option_explanations.get(o.key)` (Bilingual or empty).
- `CleanedQuestion` gains `license_status: str | None = None` carried from raw.

### load.py — write difficulty-aware + per-option-explanation translations; compare difficulty

- `_translation_payload` returns per-option explanations too: `(stem, rationale, [(content, explanation), ...])`.
- `_write_translations` writes `"explanation": sanitize_rich_text(expl, markdown)` per option (None → None, unchanged for osg10).
- `_apply_one` uses `cleaned.license_status` (parsed to `LicenseStatus`, default `unconfirmed`) instead of hardcoded `unconfirmed`.
- `_differs` gains: difficulty change → True; per-option explanation change (per language, via `_translation_payload`) → True.

## Tests (TDD)

- `test_transform.py`: source difficulty (int/label/clamp) wins; type-based fallback (multi→4, true_false→2, single→3); `option_explanations` carried per option (en/zh); missing → empty; `license_status` carried.
- `test_load.py`: per-option explanation written to translation option JSON; `_differs` detects difficulty change + per-option-explanation change (triggers update); `license_status` from source honored (default unconfirmed).
- `test_extract.py` (new or existing): `_parse_difficulty` + `option_explanations` parsing from raw record dicts.

## Out of scope

- Re-deriving difficulty for the existing seeded osg10 rows (a re-import will pick up the type-based prior via the normal update path — acceptable, idempotent after first run).
- Psychometric difficulty calibration (Phase 5 IRT).
- The #35 CSV/XLSX upload itself (separate item).
