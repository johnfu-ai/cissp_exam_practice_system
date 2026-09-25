"""ETL essay-type + papers.json loading tests (FR-ETL-18/19)."""

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.etl.extract import (
    Bilingual,
    DatasetReader,
    RawOption,
    RawQuestion,
    RawSource,
)
from app.etl.load import LoadResult, apply_load, apply_papers
from app.etl.transform import transform, validate
from app.models.enums import QuestionType
from app.models.paper import Paper, PaperQuestion

MOCKPAPERS_DIR = Path(__file__).resolve().parents[3] / "docs" / "questions" / "mockpapers"


def _raw_essay(*, ref_en="Ref answer.", ref_zh="参考答案。", with_zh=True):
    return RawQuestion(
        id="essay-1",
        source=RawSource("Book", 1, "review", 1, "Ch1", 1),
        type="essay",
        stem=Bilingual(en="Explain X.", zh="解释X。" if with_zh else ""),
        options=[],
        correct_keys=[],
        explanation=Bilingual(en="", zh=""),
        meta={},
        reference_answer=Bilingual(en=ref_en, zh=ref_zh),
    )


def _raw_choice(qid="c1"):
    return RawQuestion(
        id=qid,
        source=RawSource("Book", 1, "review", 1, "Ch1", 1),
        type="single_choice",
        stem=Bilingual(en=f"Stem {qid}", zh=""),
        options=[
            RawOption(key="A", text=Bilingual(en="a", zh="")),
            RawOption(key="B", text=Bilingual(en="b", zh="")),
        ],
        correct_keys=["A"],
        explanation=Bilingual(en="why", zh=""),
        meta={},
    )


# --- transform / validate ----------------------------------------------------


def test_transform_essay_carries_reference_answer():
    cleaned = transform(_raw_essay())
    assert cleaned.question_type is QuestionType.essay
    assert cleaned.options == []
    assert cleaned.reference_answer_en == "Ref answer."
    assert cleaned.reference_answer_zh == "参考答案。"
    assert validate(_raw_essay()) == []


def test_validate_essay_requires_reference_answer():
    raw = _raw_essay(ref_en="", ref_zh="")
    issues = validate(raw)
    assert any("reference_answer" in i for i in issues)


def test_validate_essay_rejects_options():
    raw = _raw_essay()
    raw.options = [RawOption(key="A", text=Bilingual(en="a", zh=""))]
    raw.correct_keys = ["A"]
    issues = validate(raw)
    assert any("options" in i for i in issues)


# --- extract ------------------------------------------------------------------


def test_parse_record_reads_reference_answer_and_domain_number(tmp_path):
    rec = {
        "id": "e1",
        "source": {
            "book": "B", "edition": 1, "section": "exam", "chapter": 3,
            "chapter_title": "C3", "number": 7, "domain_number": 3,
        },
        "type": "essay",
        "stem": {"en": "S?", "zh": "中文?"},
        "options": [],
        "correct_keys": [],
        "explanation": {"en": "", "zh": ""},
        "reference_answer": {"en": "R", "zh": "参考"},
    }
    from app.etl.extract import _parse_record

    raw = _parse_record(rec)
    assert raw.type == "essay"
    assert raw.reference_answer is not None
    assert raw.reference_answer.en == "R"
    assert raw.reference_answer.zh == "参考"
    assert raw.meta.get("domain") == 3  # source.domain_number -> meta.domain


@pytest.mark.skipif(not MOCKPAPERS_DIR.exists(), reason="mockpapers dataset not generated")
def test_reader_reads_mock-paper_papers_json():
    reader = DatasetReader(MOCKPAPERS_DIR)
    raws, errors, content_hash = reader.read()
    assert not errors
    assert len(raws) == 828
    papers = reader.read_papers()
    assert len(papers) == 8
    assert papers[0]["question_ids"][0].startswith("paper-")
    # content hash includes papers.json so edits to papers force a re-preview
    h2 = DatasetReader(MOCKPAPERS_DIR).read()[2]
    assert h2 == content_hash


# --- load ---------------------------------------------------------------------


def _org(session):
    from tests.test_paper_models import _org_id

    return _org_id(session)


def test_load_essay_writes_reference_answer(db_session):
    org = _org(db_session)
    cleaned = transform(_raw_essay())
    result = apply_load(db_session, org, "essayset", None, [cleaned])
    assert result.created == 1
    from sqlalchemy import select
    from app.models.question import QuestionTranslation

    rows = db_session.execute(select(QuestionTranslation)).scalars().all()
    by_lang = {t.language: t for t in rows}
    assert by_lang["en"].reference_answer == "Ref answer."
    assert by_lang["zh"].reference_answer == "参考答案。"


def test_load_papers_creates_then_idempotent(db_session):
    org = _org(db_session)
    c1 = transform(_raw_choice("p1q1"))
    c2 = transform(_raw_choice("p1q2"))
    result = apply_load(db_session, org, "paperset", None, [c1, c2])
    assert result.created == 2

    papers = [{
        "id": "paper-1", "name": "P1", "duration_minutes": 60,
        "domain_number": 1, "question_ids": ["p1q2", "p1q1"], "scores": [2, 1],
        "total_score": 3, "status": "published",
    }]
    pr = apply_papers(db_session, org, "paperset", papers, LoadResult())
    assert pr.papers_created == 1
    paper = db_session.execute(select(Paper)).scalar_one()
    assert paper.name == "P1"
    assert paper.question_count == 2
    assert paper.total_score == 3
    assert paper.dataset_slug == "paperset"
    ordered = sorted(paper.questions, key=lambda pq: pq.position)
    # paper order p1q2 first, then p1q1; scores follow positions
    assert [pq.score for pq in ordered] == [2, 1]
    assert ordered[0].position == 1

    # idempotent re-run: no duplicate rows, no error, counts as updated-or-same
    pr2 = apply_papers(db_session, org, "paperset", papers, LoadResult())
    assert pr2.papers_created == 0
    assert db_session.execute(select(Paper)).scalars().all().__len__() == 1
    assert db_session.execute(select(PaperQuestion)).scalars().all().__len__() == 2


def test_load_papers_missing_question_ref_skips_paper(db_session):
    org = _org(db_session)
    c1 = transform(_raw_choice("p2q1"))
    apply_load(db_session, org, "paperset2", None, [c1])
    papers = [{
        "id": "paper-2", "name": "P2", "duration_minutes": 60,
        "question_ids": ["p2q1", "missing-q"], "scores": [1, 1],
        "total_score": 2, "status": "published",
    }]
    pr = apply_papers(db_session, org, "paperset2", papers, LoadResult())
    assert pr.papers_created == 0
    assert any("missing-q" in str(e) for e in pr.errors)
    assert db_session.execute(select(Paper)).scalars().first() is None


@pytest.mark.skipif(not MOCKPAPERS_DIR.exists(), reason="mockpapers dataset not generated")
def test_full_pipeline_mock-paper_dataset(db_session):
    """End-to-end over the real converted dataset: extract -> transform ->
    apply_load(incl. papers) yields 828 questions + 8 papers."""
    org = _org(db_session)
    reader = DatasetReader(MOCKPAPERS_DIR)
    raws, errors, _ = reader.read()
    assert not errors
    cleaned = [transform(r) for r in raws]
    result = apply_load(db_session, org, "mockpapers", None, cleaned)
    assert result.created == 828
    pr = apply_papers(db_session, org, "mockpapers", reader.read_papers(), result)
    assert pr.papers_created == 8
    total_pq = db_session.execute(select(PaperQuestion)).scalars().all()
    assert len(total_pq) == 828
