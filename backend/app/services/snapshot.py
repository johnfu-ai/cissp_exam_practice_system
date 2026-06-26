"""Snapshot producer for historical answer integrity (NFR-DATA-01, FR-LANG-07).

Captures ALL translations + the canonical option correctness + the delivered
language mode at answer time so later edits never alter historical records.
The blob lives in JSONB and may evolve its internal shape without a migration.
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
    """Freeze a question's canonical answer key + all translations + mode.

    The canonical `options` list captures only `order_index` + `is_correct`
    (the answer key) — option *content* lives per-translation under
    `translations[lang].options` so each language is independently frozen.
    """
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
    if tmap:
        opts = []
        for co in snap.get("options", []):
            oi = co["order_index"]
            cell = {
                "order_index": oi,
                "is_correct": co["is_correct"],
                "content": {},
                "content_format": {},
                "explanation": {},
            }
            for l in ("en", "zh"):
                to = next(
                    (
                        o
                        for o in (tmap.get(l) or {}).get("options", [])
                        if o.get("order_index") == oi
                    ),
                    {},
                )
                cell["content"][l] = to.get("content")
                cell["content_format"][l] = to.get("content_format")
                cell["explanation"][l] = to.get("explanation")
            opts.append(cell)
        return {
            "stem": {l: (tmap.get(l) or {}).get("stem") for l in ("en", "zh")},
            "options": opts,
            "correct_rationale": {
                l: (tmap.get(l) or {}).get("correct_answer_rationale") for l in ("en", "zh")
            },
            "key_point_summary": {
                l: (tmap.get(l) or {}).get("key_point_summary") for l in ("en", "zh")
            },
            "available_languages": langs,
        }
    # Legacy snapshot fallback (pre-translation shape: flat stem/options).
    return {
        "stem": {"en": snap.get("stem", ""), "zh": snap.get("stem", "")},
        "options": [
            {
                "order_index": o.get("order_index"),
                "is_correct": o.get("is_correct"),
                "content": {"en": o.get("content"), "zh": o.get("content")},
                "content_format": {
                    "en": o.get("content_format"),
                    "zh": o.get("content_format"),
                },
                "explanation": {"en": None, "zh": None},
            }
            for o in snap.get("options", [])
        ],
        "correct_rationale": {"en": None, "zh": None},
        "key_point_summary": {"en": None, "zh": None},
        "available_languages": ["en"],
    }
