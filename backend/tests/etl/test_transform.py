from app.etl.extract import Bilingual, RawOption, RawQuestion, RawSource
from app.etl.transform import transform, validate
from app.models.enums import QuestionType


def _raw(type_: str, correct_keys, prompt_items=None, zh_stem="单选", zh_options=None):
    options = [
        RawOption(key="A", text=Bilingual(en="A", zh=(zh_options or {}).get("A", "甲"))),
        RawOption(key="B", text=Bilingual(en="B", zh=(zh_options or {}).get("B", "乙"))),
    ]
    return RawQuestion(
        id="t1",
        source=RawSource("Book", 1, "review", 1, "Title", 1),
        type=type_,
        stem=Bilingual(en="Stem", zh=zh_stem),
        options=options,
        correct_keys=correct_keys,
        explanation=Bilingual(en="Exp", zh="解析"),
        meta={"choose_all": False, "matching": type_ == "matching", "issues": [], "zh_source": "v9", "zh_issues": []},
        prompt_items=prompt_items,
    )


def test_matching_normalizes_to_single_choice_with_prompt_items():
    raw = _raw("matching", ["B"], prompt_items=[RawPromptItemDummy])
    # prompt_items real test below uses a raw built with prompt_items
    cleaned = transform(raw, "en")
    assert cleaned.question_type is QuestionType.single_choice
    assert cleaned.prompt_items is not None


def test_single_choice_passes_through():
    raw = _raw("single_choice", ["A"])
    cleaned = transform(raw, "en")
    assert cleaned.question_type is QuestionType.single_choice
    assert cleaned.prompt_items is None


def test_multiple_choice_passes_through():
    raw = _raw("multiple_choice", ["A", "B"])
    cleaned = transform(raw, "en")
    assert cleaned.question_type is QuestionType.multiple_choice


def test_bilingual_split_en_vs_zh():
    raw = _raw("single_choice", ["A"], zh_stem="题干")
    en = transform(raw, "en")
    zh = transform(raw, "zh")
    assert en.stem == "Stem"
    assert zh.stem == "题干"
    assert en.options[0].content == "A"
    assert zh.options[0].content == "甲"


def test_missing_zh_marks_needs_revision_and_falls_back():
    raw = _raw("single_choice", ["A"], zh_stem="", zh_options={"A": "", "B": ""})
    zh = transform(raw, "zh")
    assert zh.needs_revision is True
    assert zh.stem == "Stem"  # fell back to en
    assert "missing_zh" in zh.issues


def test_is_correct_from_correct_keys():
    raw = _raw("multiple_choice", ["A", "B"])
    cleaned = transform(raw, "en")
    assert [o.is_correct for o in cleaned.options] == [True, True]
    raw2 = _raw("single_choice", ["B"])
    cleaned2 = transform(raw2, "en")
    assert [o.is_correct for o in cleaned2.options] == [False, True]


def test_default_difficulty_and_chapter():
    raw = _raw("single_choice", ["A"])
    cleaned = transform(raw, "en")
    assert cleaned.difficulty == 3
    assert cleaned.source_chapter == 1
    assert cleaned.source_chapter_title == "Title"


def test_validate_single_choice_requires_exactly_one_correct():
    raw = _raw("single_choice", ["A", "B"])
    issues = validate(raw)
    assert any("exactly 1" in i for i in issues)


def test_validate_multiple_choice_requires_at_least_two():
    raw = _raw("multiple_choice", ["A"])
    issues = validate(raw)
    assert any("at least 2" in i for i in issues)


def test_validate_correct_keys_subset_of_options():
    raw = _raw("single_choice", ["Z"])
    issues = validate(raw)
    assert any("not in options" in i for i in issues)


# dummy used by the matching test above; replaced with real RawPromptItem
from app.etl.extract import RawPromptItem  # noqa: E402
RawPromptItemDummy = RawPromptItem(key="1", text=Bilingual(en="X", zh="X"))
