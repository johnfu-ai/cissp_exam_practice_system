"""Unit tests for Markdown paste parser (FR-IMP-02)."""

from app.etl.markdown_paste import parse_markdown_paste


def test_parse_single_question_en():
    md = """
What is CIA?
A. Confidentiality Integrity Availability
B. Central Intelligence Agency
C. Certificate Issuing Authority
D. None
Answer: A
Explanation: The triad.
"""
    rows = parse_markdown_paste(md)
    assert len(rows) == 1
    assert "CIA" in rows[0]["question_text"]
    assert rows[0]["option_a"].startswith("Confidentiality")
    assert rows[0]["correct_answers"] == "A"
    assert rows[0]["question_type"] == "single_choice"
    assert "triad" in rows[0]["explanation"]


def test_parse_zh_labels_and_multi_block():
    md = """
第一题？
A. 是
B. 否
答案: A

---

第二题？
A. 1
B. 2
C. 3
答案: A,B
解析: 多选
"""
    rows = parse_markdown_paste(md)
    assert len(rows) == 2
    assert rows[0]["correct_answers"] == "A"
    assert rows[1]["question_type"] == "multiple_choice"
    assert rows[1]["correct_answers"] == "A,B"


def test_parse_skips_incomplete_blocks():
    assert parse_markdown_paste("only a stem with no options") == []
