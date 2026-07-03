"""ETL Runner tests: one bilingual CleanedQuestion per raw, no per-language fan-out."""

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.etl.runner import EtlDriftError, run_commit, run_preview, run_rollback
from app.models.auth import Organization
from app.models.enums import ImportFormat, ImportStatus, OrgKind
from app.models.etl import ChapterDomainMapping, EtlDataset, EtlRun, QuestionExternalKey
from app.models.question import ImportJob, Question, QuestionTranslation
from app.models.taxonomy import ExamBlueprint, ExamDomain

FIXTURE = Path(__file__).parent / "fixtures" / "mini"


def _seed(session):
    org = Organization(slug="r-org", name="R", kind=OrgKind.personal)
    session.add(org)
    session.flush()
    bp = ExamBlueprint(version_label="r", effective_date=date(2024, 4, 15),
                       min_items=1, max_items=2, duration_minutes=60,
                       passing_score=700, max_score=1000, is_current=True)
    session.add(bp)
    session.flush()
    for n in (1, 2):
        session.add(ExamDomain(blueprint_id=bp.id, number=n, name=f"D{n}", weight_pct=10))
    session.flush()
    d1 = session.execute(select(ExamDomain).filter_by(number=1)).scalar_one()
    d2 = session.execute(select(ExamDomain).filter_by(number=2)).scalar_one()
    session.add(ChapterDomainMapping(dataset_slug="mini", chapter_number=1,
                                     domain_id=d1.id, chapter_title="Chapter One"))
    session.add(ChapterDomainMapping(dataset_slug="mini", chapter_number=2,
                                     domain_id=d2.id, chapter_title="Chapter Two"))
    session.flush()
    ds = EtlDataset(
        organization_id=org.id, slug="mini", name="Mini", source_path=str(FIXTURE),
        format=ImportFormat.json, total_questions=3, languages=["en", "zh"],
    )
    session.add(ds)
    session.flush()
    return org.id, ds


def _count(session, model):
    return session.execute(select(func.count()).select_from(model)).scalar_one()


def test_preview_writes_no_questions(db_session):
    org_id, ds = _seed(db_session)
    run = run_preview(db_session, org_id, ds)
    assert run.phase.value == "preview"
    assert db_session.execute(select(Question)).scalars().all() == []
    summary = run.preview_summary
    # 3 raws -> 3 bilingual cleaned records -> 3 would-create (one per external_id)
    assert summary["would_create"] == 3
    # each bilingual record increments both en and zh
    assert summary["by_language"] == {"en": 3, "zh": 3}
    assert summary["by_type"] == {"single_choice": 2, "multiple_choice": 1}
    job = db_session.get(ImportJob, run.import_job_id)
    assert job.status == ImportStatus.previewing
    assert job.total_rows == 3


def test_commit_writes_rows(db_session):
    org_id, ds = _seed(db_session)
    run = run_preview(db_session, org_id, ds)
    committed = run_commit(db_session, org_id, run.id)
    assert committed.phase.value == "committed"
    # one Question per external_id (3), one key per external_id (3), 2 translations each (6)
    assert _count(db_session, Question) == 3
    assert _count(db_session, QuestionExternalKey) == 3
    assert _count(db_session, QuestionTranslation) == 6
    job = db_session.get(ImportJob, committed.import_job_id)
    assert job.status == ImportStatus.completed
    assert job.success_count == 3


def test_commit_is_idempotent(db_session):
    org_id, ds = _seed(db_session)
    run = run_preview(db_session, org_id, ds)
    run_commit(db_session, org_id, run.id)
    run2 = run_preview(db_session, org_id, ds)
    committed = run_commit(db_session, org_id, run2.id)
    # still only 3 questions, 3 keys, 6 translations
    assert _count(db_session, Question) == 3
    assert _count(db_session, QuestionExternalKey) == 3
    assert _count(db_session, QuestionTranslation) == 6
    # second commit's import job reflects all-unchanged
    job = db_session.get(ImportJob, committed.import_job_id)
    assert job.success_count == 0  # nothing newly created
    assert job.status == ImportStatus.completed


def test_commit_update_detects_changed_stem(db_session):
    """A second commit after editing the fixture stem updates the question."""
    org_id, ds = _seed(db_session)
    run = run_preview(db_session, org_id, ds)
    run_commit(db_session, org_id, run.id)
    # mutate one question's en translation stem directly, then re-import
    q = db_session.execute(select(Question).filter_by(source="mini-ch01-q01")).scalar_one()
    en_t = db_session.execute(select(QuestionTranslation).filter_by(
        language="en", question_id=q.id)).scalar_one()
    en_t.stem = "TAMPERED"
    db_session.flush()
    run2 = run_preview(db_session, org_id, ds)
    committed = run_commit(db_session, org_id, run2.id)
    job = db_session.get(ImportJob, committed.import_job_id)
    # the tampered question now differs -> updated, others unchanged
    assert job.success_count == 0  # nothing newly created
    # still 3 questions total
    assert _count(db_session, Question) == 3


def test_rollback_flips_status_and_writes_nothing(db_session):
    org_id, ds = _seed(db_session)
    run = run_preview(db_session, org_id, ds)
    rolled = run_rollback(db_session, run.id, org_id=org_id)
    assert rolled.phase.value == "rolled_back"
    assert db_session.execute(select(Question)).scalars().all() == []
    job = db_session.get(ImportJob, rolled.import_job_id)
    assert job.status == ImportStatus.failed


def test_drift_check_raises(db_session):
    org_id, ds = _seed(db_session)
    run = run_preview(db_session, org_id, ds)
    # tamper: change stored hash so re-read hash differs
    run.preview_summary = {**run.preview_summary, "content_hash": "0" * 64}
    db_session.flush()
    with pytest.raises(EtlDriftError):
        run_commit(db_session, org_id, run.id)
