import uuid

from sqlalchemy import select

from app.etl.load import LoadResult, apply_dry_run, apply_load
from app.etl.transform import CleanedOption, CleanedQuestion
from app.models.enums import QuestionType
from app.models.question import (
    Book,
    Chapter,
    Question,
    QuestionOption,
    QuestionRevision,
)
from app.models.etl import ChapterDomainMapping, QuestionExternalKey
from app.models.taxonomy import ExamBlueprint, ExamDomain
from datetime import date


def _cleaned(external_id="c1", lang="en", stem="Stem", explanation="Exp"):
    return CleanedQuestion(
        external_id=external_id,
        language=lang,
        question_type=QuestionType.single_choice,
        stem=stem,
        options=[CleanedOption(key="A", content="A", is_correct=True),
                 CleanedOption(key="B", content="B", is_correct=False)],
        explanation=explanation,
        prompt_items=None,
        source_chapter=1,
        source_chapter_title="Chapter One",
        difficulty=3,
        issues=[],
        needs_revision=False,
    )


def _seed_org_and_domain(session):
    from app.models.auth import Organization
    from app.models.enums import OrgKind
    org = Organization(slug="t-org", name="T", kind=OrgKind.personal)
    session.add(org)
    session.flush()
    bp = ExamBlueprint(version_label="t", effective_date=date(2024, 4, 15),
                       min_items=1, max_items=2, duration_minutes=60,
                       passing_score=700, max_score=1000, is_current=True)
    session.add(bp)
    session.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="Dom1", weight_pct=10)
    session.add(dom)
    session.flush()
    cdm = ChapterDomainMapping(dataset_slug="osg10", chapter_number=1,
                               domain_id=dom.id, chapter_title="Chapter One")
    session.add(cdm)
    session.flush()
    return org.id


def test_apply_load_creates_question_and_links(db_session):
    org_id = _seed_org_and_domain(db_session)
    cleaned = [_cleaned()]
    result = apply_load(db_session, org_id, "osg10", None, cleaned)
    assert result.created == 1
    assert result.updated == 0
    assert result.unchanged == 0
    q = db_session.execute(select(Question)).scalar_one()
    assert q.stem == "Stem"
    assert q.organization_id == org_id
    # external key
    key = db_session.execute(select(QuestionExternalKey)).scalar_one()
    assert key.external_id == "c1"
    assert key.language == "en"
    assert key.question_id == q.id
    # options
    opts = db_session.execute(select(QuestionOption)).scalars().all()
    assert len(opts) == 2
    # mapping has domain_id
    from app.models.question import QuestionMapping
    mapping = db_session.execute(select(QuestionMapping)).scalar_one()
    assert mapping.domain_id is not None


def test_apply_load_update_writes_revision_and_bumps_version(db_session):
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned(stem="Old")])
    # second run with changed stem
    result = apply_load(db_session, org_id, "osg10", None, [_cleaned(stem="New")])
    assert result.updated == 1
    q = db_session.execute(select(Question)).scalar_one()
    assert q.stem == "New"
    assert q.version == 2
    rev = db_session.execute(select(QuestionRevision)).scalar_one()
    assert rev.snapshot["stem"] == "Old"


def test_apply_load_unchanged_skips_revision(db_session):
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned()])
    result = apply_load(db_session, org_id, "osg10", None, [_cleaned()])
    assert result.unchanged == 1
    assert result.updated == 0
    assert db_session.execute(select(QuestionRevision)).scalars().all() == []


def test_apply_load_error_isolation(db_session):
    org_id = _seed_org_and_domain(db_session)
    # a cleaned record with zero options would violate NOT NULL? Instead force
    # an error by reusing an external_id but a different language that collides:
    # we make a malformed cleaned whose question_type is fine but stem is set so
    # that the second record has a duplicate (external_id, language) -> handled
    # by update path, not error. Use a record whose options list causes a DB
    # error: empty options is allowed at model level, so inject a None stem.
    bad = CleanedQuestion(
        external_id="bad", language="en", question_type=QuestionType.single_choice,
        stem=None,  # type: ignore  -- will violate NOT NULL on insert
        options=[], explanation="e", prompt_items=None, source_chapter=1,
        source_chapter_title="C", difficulty=3, issues=[], needs_revision=False,
    )
    good = _cleaned()
    result = apply_load(db_session, org_id, "osg10", None, [good, bad])
    assert result.created == 1  # good one survived
    assert len(result.errors) == 1
    assert result.errors[0]["external_id"] == "bad"


def test_apply_dry_run_classifies_without_writing(db_session):
    org_id = _seed_org_and_domain(db_session)
    summary = apply_dry_run(db_session, org_id, "osg10", [_cleaned()])
    assert summary.would_create == 1
    assert summary.would_update == 0
    assert summary.unchanged == 0
    assert db_session.execute(select(Question)).scalars().all() == []
