"""ETL Transform: pure functions turning RawQuestion -> per-language CleanedQuestion.

No DB, no I/O. Deterministic: same raw in -> same cleaned out.
"""

from dataclasses import dataclass

from app.etl.extract import RawQuestion
from app.models.enums import QuestionType

DIFFICULTY_DEFAULT = 3  # medium


@dataclass
class CleanedOption:
    key: str
    content: str
    is_correct: bool


@dataclass
class CleanedQuestion:
    external_id: str
    language: str
    question_type: QuestionType
    stem: str
    options: list[CleanedOption]
    explanation: str
    prompt_items: list | None
    source_chapter: int
    source_chapter_title: str
    difficulty: int
    issues: list[str]
    needs_revision: bool


def _normalize_type(raw_type: str) -> QuestionType:
    if raw_type == "matching":
        return QuestionType.single_choice
    return QuestionType(raw_type)


def validate(raw: RawQuestion) -> list[str]:
    issues: list[str] = []
    option_keys = {o.key for o in raw.options}
    for k in raw.correct_keys:
        if k not in option_keys:
            issues.append(f"correct_key '{k}' not in options")
    if raw.type == "single_choice" or raw.type == "matching":
        if len(raw.correct_keys) != 1:
            issues.append("single_choice requires exactly 1 correct key")
    elif raw.type == "multiple_choice":
        if len(raw.correct_keys) < 2:
            issues.append("multiple_choice requires at least 2 correct keys")
    return issues


def transform(
    raw: RawQuestion,
    language: str,
    pending_translation_ids: set[str] | None = None,
) -> CleanedQuestion:
    pending_translation_ids = pending_translation_ids or set()
    issues: list[str] = list(raw.meta.get("issues", [])) + list(raw.meta.get("zh_issues", []))
    if raw.id in pending_translation_ids:
        issues.append("translation_pending")

    needs_revision = False

    def pick(en: str, zh: str) -> str:
        nonlocal needs_revision
        if language == "zh":
            if not zh or not zh.strip():
                needs_revision = True
                issues.append("missing_zh")
                return en  # fall back to en so the row is not blank
            return zh
        return en

    stem = pick(raw.stem.en, raw.stem.zh)
    explanation = pick(raw.explanation.en, raw.explanation.zh)

    options = [
        CleanedOption(
            key=o.key,
            content=pick(o.text.en, o.text.zh),
            is_correct=o.key in raw.correct_keys,
        )
        for o in raw.options
    ]

    prompt_items = None
    if raw.type == "matching" and raw.prompt_items:
        prompt_items = [
            {"key": p.key, "text": {"en": p.text.en, "zh": p.text.zh}}
            for p in raw.prompt_items
        ]

    return CleanedQuestion(
        external_id=raw.id,
        language=language,
        question_type=_normalize_type(raw.type),
        stem=stem,
        options=options,
        explanation=explanation,
        prompt_items=prompt_items,
        source_chapter=raw.source.chapter,
        source_chapter_title=raw.source.chapter_title,
        difficulty=DIFFICULTY_DEFAULT,
        issues=issues,
        needs_revision=needs_revision,
    )
