"""MockPaper export converter tests (FR-ETL-17).

Unit tests use synthetic paper-shaped records; golden tests run against the
real exports checked in at ``docs/paper_exam_exports/``.
"""

import json
from pathlib import Path

import pytest

from app.etl.paper_export import (
    convert_exports,
    normalize_rich_text,
    split_bilingual,
    strip_option_letter,
    write_dataset,
)

EXPORTS_DIR = Path(__file__).resolve().parents[3] / "docs" / "paper_exam_exports"


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestSplitBilingual:
    def test_inline_mixed_text_splits_at_first_cjk(self):
        assert split_bilingual("Corrective control 纠正性") == (
            "Corrective control", "纠正性")

    def test_two_p_blocks_split_by_block(self):
        text = "<p>Who is responsible?</p>\n<p>谁负责？</p>"
        en, zh = split_bilingual(text)
        assert en == "Who is responsible?"
        assert zh == "谁负责？"

    def test_zh_only(self):
        assert split_bilingual("对在网络上传输的数据是否需要加密的判断应该基于：") == (
            "", "对在网络上传输的数据是否需要加密的判断应该基于：")

    def test_en_only(self):
        assert split_bilingual("Plain english stem") == ("Plain english stem", "")

    def test_cjk_punctuation_only_text_is_zh(self):
        assert split_bilingual("下列哪一项不是对保密性的破坏？") == (
            "", "下列哪一项不是对保密性的破坏？")


class TestStripOptionLetter:
    def test_plain_prefix(self):
        assert strip_option_letter("A. an operational issue. 操作问题") == (
            "an operational issue. 操作问题")

    def test_chinese_enum_prefix(self):
        assert strip_option_letter("B、预防性") == "预防性"

    def test_wrapped_in_p(self):
        assert strip_option_letter("<p>C. Hardware destruction</p>") == (
            "Hardware destruction")

    def test_no_prefix_untouched(self):
        assert strip_option_letter("None of the above") == "None of the above"


class TestNormalizeRichText:
    def test_strips_msonormal_class(self):
        assert 'class' not in normalize_rich_text(
            '<p class="MsoNormal">Corrective control&nbsp;<span style="font-family: PMingLiU;">纠正性</span></p>')

    def test_nbsp_becomes_space(self):
        assert "&nbsp;" not in normalize_rich_text("a&nbsp;b")

    def test_keeps_img_https(self):
        out = normalize_rich_text('<p>x</p><p><img src="https://oss.sectv.cn/a.png"></p>')
        assert '<img src="https://oss.sectv.cn/a.png">' in out

    def test_unwraps_style_spans_keeping_content(self):
        out = normalize_rich_text(
            '<span style="font-family: PMingLiU;">预防性</span>')
        assert out.strip() == "预防性"


# ---------------------------------------------------------------------------
# Converter (synthetic)
# ---------------------------------------------------------------------------

def _synth_paper():
    return {
        "paper": {
            "id": "p1", "paperName": "模拟试卷一.安全与风险管理",
            "examDuration": 60, "totalScore": 2, "questionNum": 2,
        },
        "questions": [
            {
                "id": "q1", "sort": 1, "score": 1, "questionType": "choice",
                "type": "1",
                "questionName": "<p>Who is responsible?</p><p>谁负责？</p>",
                "questionAnswers": [
                    {"answerContent": "A. Senior management 高层管理",
                     "answerAnalysis": "", "isCorrect": 0},
                    {"answerContent": "<p>B. Data owner 数据所有者</p>",
                     "answerAnalysis": "<p>The data owner is accountable 责任人</p>",
                     "isCorrect": 1},
                ],
            },
            {
                "id": "q2", "sort": 2, "score": 1, "questionType": "choice",
                "type": "1",
                "questionName": "对在网络上传输的数据是否需要加密的判断应该基于：",
                "questionAnswers": [
                    {"answerContent": "A. 数据分类", "answerAnalysis": "", "isCorrect": 1},
                    {"answerContent": "B. ignore", "answerAnalysis": "", "isCorrect": 0},
                ],
            },
        ],
    }


class TestConvertExports:
    def test_synthetic_paper_converts_to_standard_records(self, tmp_path):
        src = tmp_path / "exports"
        src.mkdir()
        (src / "paper_p1.json").write_text(
            json.dumps(_synth_paper(), ensure_ascii=False), encoding="utf-8")
        out = tmp_path / "out"

        manifest, records, papers = convert_exports(src)

        assert manifest["total_questions"] == 2
        assert len(records) == 2
        assert len(papers) == 1

        first = records[0]
        assert first["id"] == "paper-q1"
        assert first["type"] == "single_choice"
        assert first["stem"] == {"en": "Who is responsible?", "zh": "谁负责？"}
        assert [o["key"] for o in first["options"]] == ["A", "B"]
        assert first["options"][0]["text"] == {
            "en": "Senior management", "zh": "高层管理"}
        assert first["options"][1]["text"] == {"en": "Data owner", "zh": "数据所有者"}
        assert first["correct_keys"] == ["B"]
        # explanation prefers the correct option's analysis; per-option captured
        assert first["explanation"]["zh"] == "责任人"
        assert first["option_explanations"]["B"]["zh"] == "责任人"
        assert first["source"]["book"] == "CISSP 模拟试卷"
        assert first["source"]["chapter"] == 1
        assert first["source"]["domain_number"] == 1
        assert first["license_status"] == "unconfirmed"

        paper = papers[0]
        assert paper["id"] == "p1"
        assert paper["name"] == "模拟试卷一.安全与风险管理"
        assert paper["duration_minutes"] == 60
        assert paper["question_ids"] == ["paper-q1", "paper-q2"]
        assert paper["scores"] == [1, 1]
        assert paper["total_score"] == 2
        assert paper["status"] == "published"

    def test_write_dataset_produces_standard_layout(self, tmp_path):
        src = tmp_path / "exports"
        src.mkdir()
        (src / "paper_p1.json").write_text(
            json.dumps(_synth_paper(), ensure_ascii=False), encoding="utf-8")
        out = tmp_path / "dataset"

        manifest, records, papers = convert_exports(src)
        write_dataset(out, manifest, records, papers)

        assert (out / "manifest.json").exists()
        lines = (out / "questions.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["id"] == "paper-q1"
        papers_doc = json.loads((out / "papers.json").read_text(encoding="utf-8"))
        assert papers_doc["papers"][0]["question_ids"] == ["paper-q1", "paper-q2"]

    def test_idempotent_pure_output(self, tmp_path):
        src = tmp_path / "exports"
        src.mkdir()
        (src / "paper_p1.json").write_text(
            json.dumps(_synth_paper(), ensure_ascii=False), encoding="utf-8")
        a = convert_exports(src)
        b = convert_exports(src)
        assert a == b


# ---------------------------------------------------------------------------
# Golden tests over the real exports
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not EXPORTS_DIR.exists(), reason="mock-paper exports not present")
class TestRealExports:
    def test_all_eight_papers_convert(self):
        manifest, records, papers = convert_exports(EXPORTS_DIR)
        assert len(papers) == 8
        assert manifest["total_questions"] == 828
        assert len(records) == 828
        # unique external ids
        ids = [r["id"] for r in records]
        assert len(set(ids)) == 828

    def test_every_question_has_stem_and_one_correct_choice(self):
        _, records, _ = convert_exports(EXPORTS_DIR)
        for r in records:
            assert r["type"] == "single_choice"
            assert r["stem"]["en"] or r["stem"]["zh"], r["id"]
            assert len(r["options"]) >= 2
            assert len(r["correct_keys"]) == 1
            for o in r["options"]:
                assert not o["text"]["en"].lstrip().startswith(
                    ("A.", "B.", "C.", "D.")), (r["id"], o["key"])
                assert o["text"]["en"] or o["text"]["zh"], (r["id"], o["key"])

    def test_papers_reference_existing_questions_in_order(self):
        _, records, papers = convert_exports(EXPORTS_DIR)
        known = {r["id"] for r in records}
        total = 0
        for p in papers:
            assert set(p["question_ids"]) <= known
            assert len(p["question_ids"]) == len(p["scores"])
            assert p["total_score"] == sum(p["scores"])
            assert p["duration_minutes"] > 0
            total += len(p["question_ids"])
        assert total == 828

    def test_domain_mapping_one_to_eight(self):
        _, _, papers = convert_exports(EXPORTS_DIR)
        by_domain = {p["domain_number"]: p["name"] for p in papers}
        assert sorted(by_domain) == [1, 2, 3, 4, 5, 6, 7, 8]
        assert "安全与风险管理" in by_domain[1]
        assert "开发安全" in by_domain[8]

    def test_explanations_preserved_where_source_has_them(self):
        _, records, _ = convert_exports(EXPORTS_DIR)
        with_exp = [r for r in records if r["explanation"]["en"] or r["explanation"]["zh"]]
        # spot-checked source: 292 questions carry answerAnalysis
        assert 200 <= len(with_exp) <= 828
