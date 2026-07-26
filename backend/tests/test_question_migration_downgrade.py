"""Migration test: the a1b2c3d4e5f6 bilingual-merge DOWNGRADE (reverse path).

``test_question_migration_merge`` covers the upgrade direction (an ETL en/zh pair
merges into one Question with two translations). This file covers the previously
UNTESTED reverse: downgrade from a1b2c3d4e5f6 back to dee7bc824643.

The downgrade is intentionally LOSSY - it restores only the 'en' translation
onto ``questions.stem``/``explanations`` and does NOT unpack per-option content
from ``question_translations.options`` back into ``question_options.content``.
This test pins that contract so the highest-stakes reverse path isn't a silent
dark hole (audit #22): a future change that silently widened or narrowed the
lossy downgrade would fail here.
"""
import json
import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
ADMIN = "postgresql+psycopg://cissp:cissp@localhost:5432/cissp"
MIG = "postgresql+psycopg://cissp:cissp@localhost:5432/cissp_migdown"

MERGE_REV = "a1b2c3d4e5f6"
PREV_REV = "dee7bc824643"


@pytest.fixture
def mig_engine():
    admin = create_engine(ADMIN, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text("DROP DATABASE IF EXISTS cissp_migdown"))
        c.execute(text("CREATE DATABASE cissp_migdown"))
    admin.dispose()

    eng = create_engine(MIG)
    # Stop at the merge revision so its downgrade is isolated from the four
    # later migrations (interface_language, password_reset_audit, fk_indexes,
    # unique_constraints, dedup_hashes).
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", MIG)
    command.upgrade(cfg, MERGE_REV)
    yield eng

    eng.dispose()
    admin = create_engine(ADMIN, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text("DROP DATABASE IF EXISTS cissp_migdown"))
    admin.dispose()


def _insert_bilingual_question(eng, qid, org):
    """Insert one Question with en+zh translations + 2 options at the post-merge
    (a1b2c3d4e5f6) schema: questions has NO stem/language column, question_options
    has NO content column - both live in question_translations now."""
    with eng.begin() as s:
        s.execute(
            text(
                "INSERT INTO organizations (id, name, slug, kind, status, created_at, updated_at) "
                "VALUES (:id, 'o', 'o', 'personal', 'active', now(), now())"
            ),
            {"id": org},
        )
        s.execute(
            text(
                "INSERT INTO questions "
                "(id, question_type, status, license_status, version, organization_id, "
                " available_languages, created_at, updated_at) "
                "VALUES (:id, 'single_choice', 'published', 'unconfirmed', 1, :org, "
                " ARRAY['en','zh']::varchar[], now(), now())"
            ),
            {"id": qid, "org": org},
        )
        for lang, stem, rationale in (
            ("en", "What is CIA?", "EN rationale"),
            ("zh", "什么是CIA？", "ZH rationale"),
        ):
            options = json.dumps(
                [
                    {
                        "order_index": 0,
                        "content": f"{lang}-A",
                        "is_correct": True,
                        "explanation": "ex0",
                    },
                    {"order_index": 1, "content": f"{lang}-B", "is_correct": False},
                ]
            )
            s.execute(
                text(
                    "INSERT INTO question_translations "
                    "(question_id, language, stem, stem_format, correct_answer_rationale, options, "
                    " created_at, updated_at) "
                    "VALUES (:qid, :lang, :stem, 'markdown', :rationale, CAST(:options AS jsonb), "
                    " now(), now())"
                ),
                {
                    "qid": qid,
                    "lang": lang,
                    "stem": stem,
                    "rationale": rationale,
                    "options": options,
                },
            )
        for order, correct in ((0, True), (1, False)):
            s.execute(
                text(
                    "INSERT INTO question_options "
                    "(question_id, order_index, is_correct, created_at, updated_at) "
                    "VALUES (:qid, :order, :correct, now(), now())"
                ),
                {"qid": qid, "order": order, "correct": correct},
            )


def test_bilingual_merge_downgrade_is_lossy_but_safe(mig_engine):
    qid = uuid.uuid4()
    org = uuid.uuid4()
    _insert_bilingual_question(mig_engine, qid, org)

    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", MIG)
    command.downgrade(cfg, PREV_REV)

    with mig_engine.connect() as s:
        # 'en' stem + language restored onto questions (from the en translation).
        stem, lang = s.execute(
            text("SELECT stem, language FROM questions WHERE id = :i"), {"i": qid}
        ).one()
        assert stem == "What is CIA?"
        assert lang == "en"
        # explanations table recreated; its row carries the en rationale.
        rationale = s.execute(
            text(
                "SELECT correct_answer_rationale FROM explanations WHERE question_id = :i"
            ),
            {"i": qid},
        ).scalar()
        assert rationale == "EN rationale"
        # LOSSY: option content is NOT unpacked from translations.options -> ''.
        contents = [
            r[0]
            for r in s.execute(
                text(
                    "SELECT content FROM question_options WHERE question_id = :i "
                    "ORDER BY order_index"
                ),
                {"i": qid},
            )
        ]
        assert contents == ["", ""], f"expected lossy empty content, got {contents}"
        # zh content is gone: question_translations table dropped.
        assert (
            s.execute(
                text("SELECT to_regclass('public.question_translations')")
            ).scalar()
            is None
        )
        # available_languages column dropped from questions.
        assert (
            s.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='questions' AND column_name='available_languages'"
                )
            ).scalar()
            is None
        )

    # Re-upgrade to the merge revision.
    command.upgrade(cfg, MERGE_REV)

    with mig_engine.connect() as s:
        # The lossy contract: only the 'en' translation is recreated (zh is gone
        # for good - it was never carried back through questions.stem/explanations).
        langs = sorted(
            r[0]
            for r in s.execute(
                text(
                    "SELECT language FROM question_translations WHERE question_id = :i"
                ),
                {"i": qid},
            )
        )
        assert langs == ["en"], (
            f"zh should be permanently lost on a lossy round-trip; got {langs}"
        )
        # available_languages is repopulated from the surviving (en) translation.
        al = s.execute(
            text("SELECT available_languages FROM questions WHERE id = :i"),
            {"i": qid},
        ).scalar()
        assert al == ["en"]
