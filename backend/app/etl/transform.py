"""ETL Transform: RawQuestion -> one bilingual CleanedQuestion.

Pure functions, no DB, no I/O. Deterministic: same raw in -> same cleaned out.
A single CleanedQuestion carries both en and zh content; `available_languages`
records which translations are non-empty (`zh` only when a zh stem is present).
`needs_revision` flags en-only records awaiting translation.
"""

from dataclasses import dataclass, field

from app.etl.extract import RawQuestion
from app.models.enums import QuestionType

DIFFICULTY_DEFAULT = 3  # medium


@dataclass
class CleanedOption:
    key: str
    text_en: str
    text_zh: str
    is_correct: bool


@dataclass
class CleanedQuestion:
    external_id: str
    question_type: QuestionType
    stem_en: str
    stem_zh: str
    options: list[CleanedOption]
    explanation_en: str
    explanation_zh: str
    prompt_items: list | None
    source_chapter: int
    source_chapter_title: str
    difficulty: int
    issues: list[str]
    needs_revision: bool
    available_languages: list[str] = field(default_factory=list)


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
    if raw.type in ("single_choice", "matching"):
        if len(raw.correct_keys) != 1:
            issues.append("single_choice requires exactly 1 correct key")
    elif raw.type == "multiple_choice":
        if len(raw.correct_keys) < 2:
            issues.append("multiple_choice requires at least 2 correct keys")
    return issues


def transform(raw: RawQuestion, pending_translation_ids: set[str] | None = None) -> CleanedQuestion:
    """Build one bilingual CleanedQuestion from a RawQuestion.

    `available_languages` is `["en", "zh"]` when a non-empty zh stem is present
    (translation available), else `["en"]` only. `needs_revision` is True when
    zh is missing so the loaded Question enters the `needs_revision` status.
    """
    pending_translation_ids = pending_translation_ids or set()
    issues: list[str] = list(raw.meta.get("issues", [])) + list(raw.meta.get("zh_issues", []))
    if raw.id in pending_translation_ids:
        issues.append("translation_pending")

    has_zh_stem = bool(raw.stem.zh and raw.stem.zh.strip())
    zh_option_count = sum(1 for o in raw.options if o.text.zh and o.text.zh.strip())
    has_any_zh_option = zh_option_count > 0
    has_zh = has_zh_stem or has_any_zh_option  # any *_zh field -> bilingual intended
    # PRD §10.2 rule 8 / FR-LANG-08: if any zh field is provided, the zh options
    # must be complete + 1:1 with en. Incomplete -> needs_revision (NOT blocking).
    zh_complete = has_zh_stem and zh_option_count == len(raw.options)
    needs_revision = not zh_complete
    if not has_zh:
        issues.append("missing_zh")
    elif not zh_complete:
        issues.append("partial_zh")
    available = ["en", "zh"] if has_zh else ["en"]

    prompt_items = None
    if raw.type == "matching" and raw.prompt_items:
        prompt_items = [
            {"key": p.key, "text": {"en": p.text.en, "zh": p.text.zh}}
            for p in raw.prompt_items
        ]

    return CleanedQuestion(
        external_id=raw.id,
        question_type=_normalize_type(raw.type),
        stem_en=raw.stem.en,
        stem_zh=raw.stem.zh,
        options=[
            CleanedOption(
                key=o.key,
                text_en=o.text.en,
                text_zh=o.text.zh,
                is_correct=o.key in raw.correct_keys,
            )
            for o in raw.options
        ],
        explanation_en=raw.explanation.en,
        explanation_zh=raw.explanation.zh,
        prompt_items=prompt_items,
        source_chapter=raw.source.chapter,
        source_chapter_title=raw.source.chapter_title,
        difficulty=DIFFICULTY_DEFAULT,
        issues=issues,
        needs_revision=needs_revision,
        available_languages=available,
    )
