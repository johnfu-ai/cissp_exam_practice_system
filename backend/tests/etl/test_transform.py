"""ETL Transform tests: one bilingual CleanedQuestion per raw record."""

from app.etl.extract import Bilingual, RawOption, RawPromptItem, RawQuestion, RawSource
from app.etl.transform import CleanedOption, CleanedQuestion, transform, validate
from app.models.enums import QuestionType


def _raw(*, stem_en="Stem", stem_zh="题干", opt_en=("A", "B"), opt_zh=("甲", "乙"),
         correct_keys=("A",), type_="single_choice", explanation_en="Exp",
         explanation_zh="解析", prompt_items=None, issues=None, zh_issues=None,
         qid="t1", chapter=1, chapter_title="Title"):
    options = [
        RawOption(key="A", text=Bilingual(en=opt_en[0], zh=opt_zh[0])),
        RawOption(key="B", text=Bilingual(en=opt_en[1], zh=opt_zh[1])),
    ]
    return RawQuestion(
        id=qid,
        source=RawSource("Book", 1, "review", chapter, chapter_title, 1),
        type=type_,
        stem=Bilingual(en=stem_en, zh=stem_zh),
        options=options,
        correct_keys=list(correct_keys),
        explanation=Bilingual(en=explanation_en, zh=explanation_zh),
        meta={"choose_all": False, "matching": type_ == "matching",
              "issues": issues or [], "zh_source": "v9", "zh_issues": zh_issues or []},
        prompt_items=prompt_items,
    )


def test_transform_returns_one_bilingual_record():
    raw = _raw(stem_en="en", stem_zh="中")
    c = transform(raw, set())
    assert c.external_id == raw.id
    assert c.stem_en == "en"
    assert c.stem_zh == "中"
    assert c.available_languages == ["en", "zh"]
    assert len(c.options) == len(raw.options)
    assert c.needs_revision is False


def test_transform_marks_en_only_when_zh_missing():
    raw = _raw(stem_en="en", stem_zh="", opt_zh=("", ""))
    c = transform(raw, set())
    assert c.available_languages == ["en"]
    assert c.needs_revision is True
    assert "missing_zh" in c.issues


def test_transform_marks_partial_zh_options_as_needs_revision():
    # PRD §10.2 rule 8 / FR-LANG-08: zh stem present but one zh option missing
    # -> partial, not blocking, but flagged needs_revision.
    raw = _raw(stem_en="en", stem_zh="中", opt_zh=("甲", ""))
    c = transform(raw, set())
    assert c.available_languages == ["en", "zh"]  # bilingual intended
    assert c.needs_revision is True
    assert "partial_zh" in c.issues


def test_transform_marks_partial_zh_options_only_as_needs_revision():
    # zh stem missing but a zh option present -> still partial
    raw = _raw(stem_en="en", stem_zh="", opt_zh=("甲", ""))
    c = transform(raw, set())
    assert c.available_languages == ["en", "zh"]
    assert c.needs_revision is True
    assert "partial_zh" in c.issues


def test_transform_options_carry_both_languages_and_correctness():
    raw = _raw(type_="multiple_choice", correct_keys=("A", "B"))
    c = transform(raw, set())
    assert [o.is_correct for o in c.options] == [True, True]
    assert c.options[0].text_en == "A" and c.options[0].text_zh == "甲"
    assert c.options[1].text_en == "B" and c.options[1].text_zh == "乙"
    # flip correctness
    raw2 = _raw(type_="single_choice", correct_keys=("B",))
    c2 = transform(raw2, set())
    assert [o.is_correct for o in c2.options] == [False, True]


def test_transform_matching_normalizes_to_single_choice_with_prompt_items():
    raw = _raw(
        type_="matching", correct_keys=("B",),
        prompt_items=[RawPromptItem(key="1", text=Bilingual(en="First", zh="第一"))],
    )
    c = transform(raw, set())
    assert c.question_type is QuestionType.single_choice
    assert c.prompt_items is not None
    assert c.prompt_items[0]["key"] == "1"
    assert c.prompt_items[0]["text"] == {"en": "First", "zh": "第一"}


def test_transform_single_choice_passes_through():
    raw = _raw(type_="single_choice", correct_keys=("A",))
    c = transform(raw, set())
    assert c.question_type is QuestionType.single_choice
    assert c.prompt_items is None


def test_transform_multiple_choice_passes_through():
    raw = _raw(type_="multiple_choice", correct_keys=("A", "B"))
    c = transform(raw, set())
    assert c.question_type is QuestionType.multiple_choice


def test_transform_pending_translation_flag_added():
    raw = _raw(qid="t1")
    c = transform(raw, {"t1"})
    assert "translation_pending" in c.issues


def test_transform_carries_source_chapter_and_difficulty():
    raw = _raw(chapter=7, chapter_title="Chapter Seven")
    c = transform(raw, set())
    assert c.source_chapter == 7
    assert c.source_chapter_title == "Chapter Seven"
    assert c.difficulty == 3


def test_transform_explanation_carried_bilingual():
    raw = _raw(explanation_en="why", explanation_zh="原因")
    c = transform(raw, set())
    assert c.explanation_en == "why"
    assert c.explanation_zh == "原因"


def test_transform_no_pending_ids_default():
    raw = _raw()
    c = transform(raw)  # pending_translation_ids defaults to None
    assert c.external_id == "t1"
    assert "translation_pending" not in c.issues


def test_validate_single_choice_requires_exactly_one_correct():
    raw = _raw(type_="single_choice", correct_keys=("A", "B"))
    issues = validate(raw)
    assert any("exactly 1" in i for i in issues)


def test_validate_multiple_choice_requires_at_least_two():
    raw = _raw(type_="multiple_choice", correct_keys=("A",))
    issues = validate(raw)
    assert any("at least 2" in i for i in issues)


def test_validate_correct_keys_subset_of_options():
    raw = _raw(type_="single_choice", correct_keys=("Z",))
    issues = validate(raw)
    assert any("not in options" in i for i in issues)


def test_validate_matching_requires_exactly_one_correct():
    raw = _raw(type_="matching", correct_keys=("A", "B"))
    issues = validate(raw)
    assert any("exactly 1" in i for i in issues)


def test_cleaned_option_dataclass_fields():
    o = CleanedOption(key="A", text_en="x", text_zh="y", is_correct=True)
    assert o.key == "A" and o.text_en == "x" and o.text_zh == "y" and o.is_correct is True


def test_cleaned_question_dataclass_fields():
    c = CleanedQuestion(
        external_id="e", question_type=QuestionType.single_choice, stem_en="s",
        stem_zh="t", options=[], explanation_en="a", explanation_zh="b",
        prompt_items=None, source_chapter=1, source_chapter_title="T", difficulty=3,
        issues=[], needs_revision=False, available_languages=["en", "zh"],
    )
    assert c.available_languages == ["en", "zh"]
    assert c.options == []
