import pytest
from sqlalchemy import inspect

from app.models.etl import (
    ChapterDomainMapping,
    EtlDataset,
    EtlRun,
    QuestionExternalKey,
)
from app.models.question import Question


def test_question_has_prompt_items_column():
    cols = {c.name for c in inspect(Question).columns}
    assert "prompt_items" in cols


def test_etl_dataset_columns():
    cols = {c.name for c in inspect(EtlDataset).columns}
    for name in [
        "id", "organization_id", "slug", "name", "source_path",
        "format", "total_questions", "languages", "notes",
        "created_at", "updated_at",
    ]:
        assert name in cols


def test_etl_run_columns():
    cols = {c.name for c in inspect(EtlRun).columns}
    for name in [
        "id", "organization_id", "dataset_id", "import_job_id",
        "phase", "preview_summary", "committed_at", "created_at", "updated_at",
    ]:
        assert name in cols


def test_question_external_key_is_global_and_unique():
    # GLOBAL = no organization_id column
    cols = {c.name for c in inspect(QuestionExternalKey).columns}
    assert "organization_id" not in cols
    for name in ["id", "dataset_slug", "external_id", "language", "question_id"]:
        assert name in cols


def test_chapter_domain_mapping_is_global():
    cols = {c.name for c in inspect(ChapterDomainMapping).columns}
    assert "organization_id" not in cols
    for name in ["id", "dataset_slug", "chapter_number", "domain_id", "chapter_title"]:
        assert name in cols
