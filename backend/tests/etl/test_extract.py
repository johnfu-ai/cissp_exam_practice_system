from pathlib import Path

from app.etl.extract import DatasetReader, ExtractError, RawQuestion, _parse_record

FIXTURE = Path(__file__).parent / "fixtures" / "mini"


def test_read_returns_raws_and_errors():
    raws, errors, content_hash = DatasetReader(FIXTURE).read()
    assert len(raws) == 3
    assert len(errors) == 1
    assert isinstance(errors[0], ExtractError)
    assert errors[0].line_no == 4


def test_raw_question_types_and_bilingual():
    raws, _, _ = DatasetReader(FIXTURE).read()
    single = next(r for r in raws if r.id == "mini-ch01-q01")
    assert single.type == "single_choice"
    assert single.stem.en == "Single?"
    assert single.stem.zh == "单选？"
    assert single.options[0].key == "A"
    assert single.options[0].text.zh == "是"
    assert single.correct_keys == ["A"]


def test_matching_record_has_prompt_items():
    raws, _, _ = DatasetReader(FIXTURE).read()
    match = next(r for r in raws if r.id == "mini-ch02-q01")
    assert match.type == "matching"
    assert match.prompt_items is not None
    assert match.prompt_items[0].key == "1"
    assert match.prompt_items[0].text.zh == "第一"


def test_content_hash_stable():
    _, _, h1 = DatasetReader(FIXTURE).read()
    _, _, h2 = DatasetReader(FIXTURE).read()
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


# --- Enrichment fields: difficulty / option_explanations / license (#16, #18) --
# All three are optional; absence -> None (defaults applied downstream).
# PRD §10 import template: `difficulty` (default medium), `option_explanations`
# + `option_explanations_zh` (JSON keyed by option key), `license_status`.

def _base_rec(**over):
    rec = {
        "id": "e1",
        "source": {"book": "B", "edition": 1, "section": "review",
                   "chapter": 1, "chapter_title": "T", "number": 1},
        "type": "single_choice",
        "stem": {"en": "s", "zh": "题"},
        "options": [{"key": "A", "text": {"en": "a", "zh": "甲"}},
                    {"key": "B", "text": {"en": "b", "zh": "乙"}}],
        "correct_keys": ["A"],
        "explanation": {"en": "e", "zh": "解"},
        "meta": {"issues": [], "zh_issues": []},
    }
    rec.update(over)
    return rec


def test_parse_record_no_enrichment_defaults_to_none():
    raw = _parse_record(_base_rec())
    assert raw.difficulty is None
    assert raw.option_explanations is None
    assert raw.license_status is None


def test_parse_record_reads_integer_difficulty():
    raw = _parse_record(_base_rec(difficulty=4))
    assert raw.difficulty == 4


def test_parse_record_reads_numeric_string_difficulty():
    raw = _parse_record(_base_rec(difficulty="2"))
    assert raw.difficulty == 2


def test_parse_record_reads_label_difficulty():
    raw = _parse_record(_base_rec(difficulty="hard"))
    assert raw.difficulty == 4
    raw = _parse_record(_base_rec(difficulty="easy"))
    assert raw.difficulty == 2
    raw = _parse_record(_base_rec(difficulty="medium"))
    assert raw.difficulty == 3


def test_parse_record_clamps_out_of_range_difficulty():
    raw = _parse_record(_base_rec(difficulty=9))
    assert raw.difficulty == 5
    raw = _parse_record(_base_rec(difficulty=0))
    assert raw.difficulty == 1


def test_parse_record_garbage_difficulty_is_none():
    raw = _parse_record(_base_rec(difficulty="nope"))
    assert raw.difficulty is None


def test_parse_record_reads_difficulty_from_meta():
    raw = _parse_record(_base_rec(meta={"issues": [], "zh_issues": [], "difficulty": 5}))
    assert raw.difficulty == 5


def test_parse_record_reads_split_option_explanations():
    # PRD §10 template: option_explanations (en) + option_explanations_zh (zh),
    # each a {key: text} map.
    raw = _parse_record(_base_rec(
        option_explanations={"A": "A is wrong", "B": "B is right"},
        option_explanations_zh={"A": "A 错", "B": "B 对"},
    ))
    assert raw.option_explanations is not None
    assert raw.option_explanations["A"].en == "A is wrong"
    assert raw.option_explanations["A"].zh == "A 错"
    assert raw.option_explanations["B"].zh == "B 对"


def test_parse_record_reads_nested_option_explanations():
    # Alternate shape: {key: {en, zh}}.
    raw = _parse_record(_base_rec(
        option_explanations={"A": {"en": "A en", "zh": "A 中"}},
    ))
    assert raw.option_explanations["A"].en == "A en"
    assert raw.option_explanations["A"].zh == "A 中"


def test_parse_record_reads_license_status():
    raw = _parse_record(_base_rec(license_status="third_party_licensed"))
    assert raw.license_status == "third_party_licensed"
