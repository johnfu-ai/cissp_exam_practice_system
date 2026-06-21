from pathlib import Path

from app.etl.extract import DatasetReader, ExtractError, RawQuestion

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
