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
    user = uuid.uuid4()      # primary-newer / secondary-older uqs case
    user2 = uuid.uuid4()     # primary-older / secondary-newer uqs case (the B3 bug)
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
        # Users — at prior head dee7bc824643 the users table has NO language_mode column.
        for uid, email in ((user, "u@x.io"), (user2, "u2@x.io")):
            s.execute(
                text(
                    "INSERT INTO users (id, email, status, created_at, updated_at) "
                    "VALUES (:id, :email, 'active', now(), now())"
                ),
                {"id": uid, "email": email},
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

        # FK targets for the child rows: an exam blueprint, a practice session, and an
        # exam session. The secondary (zh) half will carry one row in each child table.
        bp = uuid.uuid4()
        s.execute(
            text(
                "INSERT INTO exam_blueprints "
                "(id, version_label, effective_date, min_items, max_items, duration_minutes, "
                " passing_score, max_score, is_current, created_at, updated_at) "
                "VALUES (:id, 't', '2024-04-15', 1, 2, 60, 700, 1000, true, now(), now())"
            ),
            {"id": bp},
        )
        psess = uuid.uuid4()
        s.execute(
            text(
                "INSERT INTO practice_sessions "
                "(id, user_id, organization_id, created_at, updated_at) "
                "VALUES (:id, :uid, :org, now(), now())"
            ),
            {"id": psess, "uid": user, "org": org},
        )
        esess = uuid.uuid4()
        s.execute(
            text(
                "INSERT INTO exam_sessions "
                "(id, user_id, organization_id, blueprint_id, session_kind, created_at, updated_at) "
                "VALUES (:id, :uid, :org, :bp, 'fixed', now(), now())"
            ),
            {"id": esess, "uid": user, "org": org, "bp": bp},
        )

        # One child row of each kind on the SECONDARY (zh) half — after the merge these
        # must all be repointed onto the primary (en) question_id. NOT NULL JSONB columns
        # are filled with empty literals so the rows satisfy the schema.
        s.execute(
            text(
                "INSERT INTO practice_answers "
                "(id, session_id, user_id, question_id, question_snapshot, options_snapshot, "
                " created_at, updated_at) "
                "VALUES (:id, :sid, :uid, :qid, '{}'::jsonb, '[]'::jsonb, now(), now())"
            ),
            {"id": uuid.uuid4(), "sid": psess, "uid": user, "qid": q_zh},
        )
        s.execute(
            text(
                "INSERT INTO exam_answers "
                "(id, session_id, user_id, question_id, question_snapshot, options_snapshot, "
                " created_at, updated_at) "
                "VALUES (:id, :sid, :uid, :qid, '{}'::jsonb, '[]'::jsonb, now(), now())"
            ),
            {"id": uuid.uuid4(), "sid": esess, "uid": user, "qid": q_zh},
        )
        s.execute(
            text(
                "INSERT INTO question_feedback "
                "(id, question_id, organization_id, feedback_type, created_at, updated_at) "
                "VALUES (:id, :qid, :org, 'other', now(), now())"
            ),
            {"id": uuid.uuid4(), "qid": q_zh, "org": org},
        )
        s.execute(
            text(
                "INSERT INTO question_revisions "
                "(id, question_id, revision_number, snapshot, created_at, updated_at) "
                "VALUES (:id, :qid, 1, '{}'::jsonb, now(), now())"
            ),
            {"id": uuid.uuid4(), "qid": q_zh},
        )

        # user_question_states on BOTH halves for the same user with different
        # updated_at — the B3 case. The pre-fix migration always kept the primary's
        # row, silently dropping a user's newer zh-side state. Two users exercise both
        # directions of the updated_at comparison:
        #   user  -> primary newer, secondary older  (primary must be kept)
        #   user2 -> primary older, secondary newer  (secondary must win, B3 bug)
        older = "now() - interval '2 hours'"
        newer = "now()"
        s.execute(
            text(
                "INSERT INTO user_question_states "
                "(id, user_id, question_id, note, created_at, updated_at) "
                f"VALUES (:id, :uid, :qid, 'en-new', now(), {newer})"
            ),
            {"id": uuid.uuid4(), "uid": user, "qid": q_en},
        )
        s.execute(
            text(
                "INSERT INTO user_question_states "
                "(id, user_id, question_id, note, created_at, updated_at) "
                f"VALUES (:id, :uid, :qid, 'zh-old', now(), {older})"
            ),
            {"id": uuid.uuid4(), "uid": user, "qid": q_zh},
        )
        s.execute(
            text(
                "INSERT INTO user_question_states "
                "(id, user_id, question_id, note, created_at, updated_at) "
                f"VALUES (:id, :uid, :qid, 'en-old', now(), {older})"
            ),
            {"id": uuid.uuid4(), "uid": user2, "qid": q_en},
        )
        s.execute(
            text(
                "INSERT INTO user_question_states "
                "(id, user_id, question_id, note, created_at, updated_at) "
                f"VALUES (:id, :uid, :qid, 'zh-new', now(), {newer})"
            ),
            {"id": uuid.uuid4(), "uid": user2, "qid": q_zh},
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
        assert live_id == q_en, "the English question should be the surviving primary"
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

        # All secondary (zh-half) children were repointed onto the primary question_id:
        # none reference the soft-deleted q_zh, each table still has its one row.
        for table in ("practice_answers", "exam_answers", "question_feedback", "question_revisions"):
            total = s.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            assert total == 1, f"{table}: expected 1 row, got {total}"
            on_sec = s.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE question_id = :qid"),
                {"qid": q_zh},
            ).scalar()
            assert on_sec == 0, f"{table}: expected 0 rows on the soft-deleted secondary, got {on_sec}"
            on_pri = s.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE question_id = :qid"),
                {"qid": live_id},
            ).scalar()
            assert on_pri == 1, f"{table}: expected 1 row on the primary, got {on_pri}"

        # B3: the newer user_question_states row survives on the primary for each user.
        #   user  -> primary was newer ('en-new')  : kept, secondary ('zh-old') dropped.
        #   user2 -> secondary was newer ('zh-new') : wins and is repointed onto the primary.
        uqs = s.execute(
            text(
                "SELECT user_id, note FROM user_question_states WHERE question_id = :qid"
            ),
            {"qid": live_id},
        ).all()
        uqs_by_user = {r[0]: r[1] for r in uqs}
        assert set(uqs_by_user) == {user, user2}, f"uqs users={set(uqs_by_user)}"
        assert uqs_by_user[user] == "en-new", f"user: kept wrong row {uqs_by_user[user]}"
        assert uqs_by_user[user2] == "zh-new", f"user2: kept wrong row {uqs_by_user[user2]}"
        # No uqs rows left on the soft-deleted secondary.
        uqs_on_sec = s.execute(
            text("SELECT COUNT(*) FROM user_question_states WHERE question_id = :qid"),
            {"qid": q_zh},
        ).scalar()
        assert uqs_on_sec == 0, f"uqs on secondary: expected 0, got {uqs_on_sec}"

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


def test_migration_collapses_all_soft_deleted_pair_to_one_external_key(mig_engine):
    """B2: when BOTH questions in a (dataset_slug, external_id) group are already
    soft-deleted, the merge DO block's primary SELECT (which filters
    q.deleted_at IS NULL) finds no live primary, the secondary loop never runs, and
    two external_key rows survive on the same group — which would abort the new
    unique constraint. The safety-net DELETE must keep exactly one row per group so
    the constraint can be created.
    """
    org = uuid.uuid4()
    q_a = uuid.uuid4()
    q_b = uuid.uuid4()

    with mig_engine.begin() as s:
        s.execute(
            text(
                "INSERT INTO organizations (id, name, slug, kind, status, created_at, updated_at) "
                "VALUES (:id, 'o2', 'o2', 'personal', 'active', now(), now())"
            ),
            {"id": org},
        )
        # Two questions, BOTH soft-deleted up front (deleted_at set).
        for qid, lang in ((q_a, "en"), (q_b, "zh")):
            s.execute(
                text(
                    "INSERT INTO questions "
                    "(id, question_type, stem, stem_format, difficulty, language, status, "
                    " license_status, version, organization_id, deleted_at, created_at, updated_at) "
                    "VALUES "
                    "(:id, 'single_choice', :stem, 'markdown', 3, :lang, 'published', "
                    " 'unconfirmed', 1, :org, now(), now(), now())"
                ),
                {"id": qid, "stem": f"s-{lang}", "lang": lang, "org": org},
            )
        # Two external_key rows on the same group -> the multi-key case the safety net
        # must collapse.
        for qid, lang in ((q_a, "en"), (q_b, "zh")):
            s.execute(
                text(
                    "INSERT INTO question_external_keys "
                    "(dataset_slug, external_id, language, question_id, created_at, updated_at) "
                    "VALUES ('osg10', 'q2', :lang, :qid, now(), now())"
                ),
                {"qid": qid, "lang": lang},
            )

    # The migration must NOT abort on the duplicate group.
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", MIG)
    command.upgrade(cfg, "a1b2c3d4e5f6")

    with mig_engine.begin() as s:
        # Exactly one external_key row for the all-soft-deleted group survives.
        qek = s.execute(
            text(
                "SELECT dataset_slug, external_id, question_id "
                "FROM question_external_keys WHERE dataset_slug = 'osg10' AND external_id = 'q2'"
            )
        ).all()
        assert len(qek) == 1, f"expected 1 external_key for the soft-deleted group, got {len(qek)}"
        # The survivor points at one of the two (now soft-deleted) questions.
        assert qek[0][2] in (q_a, q_b)

        # No live question (both were soft-deleted and stay soft-deleted).
        live = s.execute(
            text("SELECT COUNT(*) FROM questions WHERE deleted_at IS NULL")
        ).scalar()
        assert live == 0, f"expected 0 live questions, got {live}"

        # The new 2-column unique constraint exists (the migration completed).
        exists = s.execute(
            text(
                "SELECT 1 FROM pg_constraint WHERE conname = 'uq_qek_dataset_ext'"
            )
        ).scalar()
        assert exists == 1, "uq_qek_dataset_ext unique constraint should exist"
