"""Migration test: ETL en/zh question pairs merge into one Question + two translations.

Verifies the a1b2c3d4e5f6 migration's data-merge logic by building the
pre-migration schema (head dee7bc824643), inserting two questions (one en, one
zh) sharing the same (dataset_slug, external_id) via two question_external_keys
rows, each with options + an explanation, then upgrading and asserting the
result is exactly one non-deleted question with two translations (en + zh).
"""
import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

import app.models  # noqa: F401  -- registers all tables on Base.metadata
from app.db.base import Base  # noqa: F401

ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
ADMIN = "postgresql+psycopg://cissp:cissp@localhost:5432/cissp"
MIG = "postgresql+psycopg://cissp:cissp@localhost:5432/cissp_migmerge"


@pytest.fixture
def mig_engine():
    admin = create_engine(ADMIN, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text("DROP DATABASE IF EXISTS cissp_migmerge"))
        c.execute(text("CREATE DATABASE cissp_migmerge"))
    admin.dispose()

    eng = create_engine(MIG)
    # Build ONLY the pre-migration schema by upgrading to the prior head.
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", MIG)
    command.upgrade(cfg, "dee7bc824643")
    yield eng

    eng.dispose()
    admin = create_engine(ADMIN, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text("DROP DATABASE IF EXISTS cissp_migmerge"))
    admin.dispose()


def test_merges_etl_pair_and_repoints_children(mig_engine):
    org = uuid.uuid4()
    user = uuid.uuid4()
    q_en = uuid.uuid4()
    q_zh = uuid.uuid4()

    with mig_engine.begin() as s:
        # Organization (FK target for questions.organization_id).
        s.execute(
            text(
                "INSERT INTO organizations (id, name, slug, kind, status, created_at, updated_at) "
                "VALUES (:id, 'o', 'o', 'personal', 'active', now(), now())"
            ),
            {"id": org},
        )
        # User — at prior head dee7bc824643 the users table has NO language_mode column.
        s.execute(
            text(
                "INSERT INTO users (id, email, status, created_at, updated_at) "
                "VALUES (:id, 'u@x.io', 'active', now(), now())"
            ),
            {"id": user},
        )

        # Two questions: one English, one Chinese. Both belong to the org.
        # Columns at prior head: question_type, stem, stem_format, difficulty, language,
        # status, source, license_status, import_job_id, version, id, organization_id,
        # created_at, updated_at, deleted_at, created_by_id, updated_by_id, reviewed_by_id,
        # prompt_items.
        for qid, lang, stem in ((q_en, "en", "What is CIA?"), (q_zh, "zh", "什么是CIA？")):
            s.execute(
                text(
                    "INSERT INTO questions "
                    "(id, question_type, stem, stem_format, difficulty, language, status, "
                    " license_status, version, organization_id, created_at, updated_at) "
                    "VALUES "
                    "(:id, 'single_choice', :stem, 'markdown', 3, :lang, 'published', "
                    " 'unconfirmed', 1, :org, now(), now())"
                ),
                {"id": qid, "stem": stem, "lang": lang, "org": org},
            )
            # Two options per question.
            for order, (content, is_correct) in enumerate(
                (("Confidentiality", True), ("Availability", False))
            ):
                s.execute(
                    text(
                        "INSERT INTO question_options "
                        "(question_id, order_index, content, content_format, is_correct, "
                        " created_at, updated_at) "
                        "VALUES (:qid, :order, :content, 'markdown', :correct, now(), now())"
                    ),
                    {"qid": qid, "order": order, "content": content, "correct": is_correct},
                )
            # One explanation per question.
            s.execute(
                text(
                    "INSERT INTO explanations "
                    "(question_id, correct_answer_rationale, key_point_summary, further_reading, "
                    " created_at, updated_at) "
                    "VALUES (:qid, :rationale, NULL, NULL, now(), now())"
                ),
                {"qid": qid, "rationale": f"rationale-{lang}"},
            )

        # Two question_external_keys rows sharing (dataset_slug='osg10', external_id='q1')
        # but differing on language — this is the ETL en/zh pair the merge collapses.
        for qid, lang in ((q_en, "en"), (q_zh, "zh")):
            s.execute(
                text(
                    "INSERT INTO question_external_keys "
                    "(dataset_slug, external_id, language, question_id, created_at, updated_at) "
                    "VALUES ('osg10', 'q1', :lang, :qid, now(), now())"
                ),
                {"qid": qid, "lang": lang},
            )

    # Apply the new migration.
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", MIG)
    command.upgrade(cfg, "a1b2c3d4e5f6")

    with mig_engine.begin() as s:
        rows = s.execute(
            text("SELECT id, available_languages FROM questions WHERE deleted_at IS NULL")
        ).all()
        assert len(rows) == 1, f"expected 1 live question, got {len(rows)}"
        live_id, langs = rows[0]
        # available_languages should contain both en and zh, sorted.
        assert set(langs) == {"en", "zh"}, f"available_languages={langs}"

        trans = s.execute(
            text("SELECT language, stem FROM question_translations WHERE question_id = :id"),
            {"id": live_id},
        ).all()
        trans_langs = {t[0] for t in trans}
        assert trans_langs == {"en", "zh"}, f"translation languages={trans_langs}"

        # Exactly one external_key row remains, on the live question, language nullable now.
        qek = s.execute(
            text(
                "SELECT dataset_slug, external_id, language, question_id "
                "FROM question_external_keys"
            )
        ).all()
        assert len(qek) == 1, f"expected 1 external_key row, got {len(qek)}"
        assert qek[0][0] == "osg10"
        assert qek[0][1] == "q1"
        assert qek[0][2] in ("en", None)  # primary's language kept (en preferred)
        assert qek[0][3] == live_id

        # No options or explanations left on the soft-deleted secondary question's id
        # (its options/explanations were deleted; explanations table is dropped entirely).
        # The live question's options were also dropped from question_options (content
        # columns removed); options now live only inside question_translations.options JSONB.
        opt_count = s.execute(
            text("SELECT COUNT(*) FROM question_options")
        ).scalar()
        assert opt_count == 2, f"expected 2 option rows on the live question, got {opt_count}"

        # explanations table is gone.
        tables = s.execute(
            text(
                "SELECT to_regclass('public.explanations')"
            )
        ).scalar()
        assert tables is None, "explanations table should be dropped"
