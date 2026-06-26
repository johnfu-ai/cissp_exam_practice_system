"""question_translations

Revision ID: a1b2c3d4e5f6
Revises: dee7bc824643
Create Date: 2026-06-26

Merges single-language question content (questions.stem/options/explanations)
into one Question per logical question with one row per language in
question_translations. ETL-imported en/zh pairs sharing (dataset_slug,
external_id) are merged onto the primary (English) question and child rows
(practice/exam answers, feedback, mappings, revisions, user_question_states)
are repointed. The explanations table and the single-language columns on
questions/question_options are dropped. users.language_mode is added and
question_external_keys becomes unique on (dataset_slug, external_id) with
language nullable.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a1b2c3d4e5f6'
down_revision = 'dee7bc824643'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create question_translations.
    op.create_table(
        'question_translations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column('question_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('language', sa.String(length=5), nullable=False),
        sa.Column('stem', sa.Text(), nullable=False),
        sa.Column('stem_format', postgresql.ENUM('plain', 'markdown', name='text_format', create_type=False), nullable=False, server_default='markdown'),
        sa.Column('correct_answer_rationale', sa.Text(), nullable=False),
        sa.Column('key_point_summary', sa.Text(), nullable=True),
        sa.Column('further_reading', sa.Text(), nullable=True),
        sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('question_id', 'language', name='uq_question_translations_qid_lang'),
    )

    # 2. Backfill one translation per existing Question from its stem/options/Explanation.
    op.execute("""
    INSERT INTO question_translations (question_id, language, stem, stem_format, correct_answer_rationale, key_point_summary, further_reading, options)
    SELECT q.id,
           q.language,
           q.stem,
           q.stem_format,
           COALESCE(e.correct_answer_rationale, ''),
           e.key_point_summary,
           e.further_reading,
           COALESCE((
             SELECT jsonb_agg(jsonb_build_object(
               'order_index', o.order_index,
               'content', o.content,
               'content_format', o.content_format,
               'explanation', o.explanation
             ) ORDER BY o.order_index)
             FROM question_options o WHERE o.question_id = q.id
           ), '[]'::jsonb)
    FROM questions q
    LEFT JOIN explanations e ON e.question_id = q.id
    WHERE q.deleted_at IS NULL;
    """)

    # 3. Merge ETL en/zh pairs: for each (dataset_slug, external_id) with >1 QuestionExternalKey,
    #    pick a primary (English preferred, else earliest), attach the secondary's translation onto
    #    the primary, repoint children, delete the secondary's options/explanations/external_key,
    #    and soft-delete the secondary question.
    op.execute(r"""
    DO $$
    DECLARE
        grp RECORD;
        primary_id UUID;
        sec_id UUID;
        primary_lang TEXT;
        sec_lang TEXT;
    BEGIN
        FOR grp IN
            SELECT dataset_slug, external_id
            FROM question_external_keys
            GROUP BY dataset_slug, external_id
            HAVING COUNT(*) > 1
        LOOP
            -- primary = the 'en' row, else the earliest by created_at.
            SELECT qek.question_id, qek.language INTO primary_id, primary_lang
            FROM question_external_keys qek
            JOIN questions q ON q.id = qek.question_id AND q.deleted_at IS NULL
            WHERE qek.dataset_slug = grp.dataset_slug AND qek.external_id = grp.external_id
            ORDER BY (qek.language <> 'en'), q.created_at ASC
            LIMIT 1;

            FOR sec_id, sec_lang IN
                SELECT qek.question_id, qek.language
                FROM question_external_keys qek
                WHERE qek.dataset_slug = grp.dataset_slug
                  AND qek.external_id = grp.external_id
                  AND qek.question_id <> primary_id
            LOOP
                -- Move the secondary's translation onto the primary (rename language if needed).
                UPDATE question_translations
                   SET question_id = primary_id
                 WHERE question_id = sec_id;
                -- If a same-language translation already exists on primary, drop the duplicate
                -- (keep the one with the smaller id, i.e. the primary's original).
                DELETE FROM question_translations qt
                 USING question_translations qt2
                 WHERE qt.question_id = primary_id AND qt2.question_id = primary_id
                   AND qt.language = qt2.language AND qt.id < qt2.id;

                -- Repoint user_question_states, deduping on (user_id, question_id)
                -- by keeping the row with the LATER updated_at (tie -> keep the
                -- primary's). The uq_user_question_state unique constraint would
                -- otherwise fire when both halves carry a row for the same user;
                -- always keeping the primary's (the pre-fix behaviour) discards a
                -- user's newer zh-side state. (a) drop the secondary's row when
                -- the primary's is newer-or-equal; (b) drop the primary's row when
                -- the secondary's is strictly newer; (c) repoint the survivor.
                DELETE FROM user_question_states s
                 USING user_question_states p
                 WHERE s.question_id = sec_id AND p.question_id = primary_id
                   AND s.user_id = p.user_id AND p.updated_at >= s.updated_at;
                DELETE FROM user_question_states p
                 USING user_question_states s
                 WHERE p.question_id = primary_id AND s.question_id = sec_id
                   AND p.user_id = s.user_id AND s.updated_at > p.updated_at;
                UPDATE user_question_states SET question_id = primary_id WHERE question_id = sec_id;

                -- Repoint remaining children.
                UPDATE practice_answers SET question_id = primary_id WHERE question_id = sec_id;
                UPDATE exam_answers SET question_id = primary_id WHERE question_id = sec_id;
                UPDATE question_feedback SET question_id = primary_id WHERE question_id = sec_id;
                UPDATE question_mappings SET question_id = primary_id WHERE question_id = sec_id;
                UPDATE question_revisions SET question_id = primary_id WHERE question_id = sec_id;

                -- Remove secondary's own option/explanation/external_key rows.
                DELETE FROM question_options WHERE question_id = sec_id;
                DELETE FROM explanations WHERE question_id = sec_id;
                DELETE FROM question_external_keys WHERE question_id = sec_id;

                -- Soft-delete the secondary question.
                UPDATE questions SET deleted_at = now() WHERE id = sec_id;
            END LOOP;
        END LOOP;
    END $$;
    """)

    # 4. Add available_languages column on questions, then populate from translations.
    op.add_column('questions', sa.Column('available_languages', postgresql.ARRAY(sa.String(length=5)), nullable=True))
    op.execute("""
    UPDATE questions q
       SET available_languages = sub.langs
      FROM (SELECT question_id, array_agg(language ORDER BY language) AS langs
              FROM question_translations GROUP BY question_id) sub
     WHERE sub.question_id = q.id AND q.deleted_at IS NULL;
    """)
    op.create_index('ix_questions_available_languages', 'questions', ['available_languages'], postgresql_using='gin')

    # 5. Drop single-language content columns from questions.
    op.drop_column('questions', 'stem')
    op.drop_column('questions', 'stem_format')
    op.drop_column('questions', 'language')

    # 6. Drop content/content_format/explanation from question_options.
    op.drop_column('question_options', 'content')
    op.drop_column('question_options', 'content_format')
    op.drop_column('question_options', 'explanation')

    # 7. Add users.language_mode.
    op.add_column('users', sa.Column('language_mode', sa.String(length=16), nullable=False, server_default=sa.text("'en'")))

    # 8. question_external_keys: drop old 3-col unique, make language nullable, add 2-col unique.
    op.drop_constraint('uq_qek_dataset_ext_lang', 'question_external_keys', type_='unique')
    op.alter_column('question_external_keys', 'language', existing_type=sa.String(length=5), nullable=True)
    # Safety net: the merge DO block in step 3 only collapses groups that have a
    # LIVE primary (its primary SELECT filters q.deleted_at IS NULL). If BOTH
    # questions in a (dataset_slug, external_id) group were already soft-deleted
    # before this migration, primary_id stays NULL, the secondary loop never runs,
    # and two external_key rows survive on the same group — which would make the
    # unique constraint below abort. Keep only the earliest (min-id) row per group
    # so the constraint can be created regardless of prior soft-deletes. (uuid has
    # no min() aggregate, so use ROW_NUMBER() ordered by id.)
    op.execute("""
    DELETE FROM question_external_keys
     WHERE id IN (
       SELECT id FROM (
         SELECT id,
                ROW_NUMBER() OVER (
                  PARTITION BY dataset_slug, external_id
                  ORDER BY id
                ) AS rn
           FROM question_external_keys
       ) x
        WHERE x.rn > 1
     );
    """)
    op.create_unique_constraint('uq_qek_dataset_ext', 'question_external_keys', ['dataset_slug', 'external_id'])

    # 9. Drop explanations table.
    op.drop_table('explanations')


def downgrade() -> None:
    # Recreate explanations and single-language columns (best-effort from 'en' translation).
    op.create_table(
        'explanations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column('question_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('correct_answer_rationale', sa.Text(), nullable=False),
        sa.Column('key_point_summary', sa.Text(), nullable=True),
        sa.Column('further_reading', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column('questions', sa.Column('stem', sa.Text(), nullable=False, server_default=''))
    op.add_column('questions', sa.Column('stem_format', postgresql.ENUM('plain', 'markdown', name='text_format', create_type=False), nullable=False, server_default='markdown'))
    op.add_column('questions', sa.Column('language', sa.String(length=5), nullable=False, server_default=sa.text("'en'")))
    op.add_column('question_options', sa.Column('content', sa.Text(), nullable=False, server_default=''))
    op.add_column('question_options', sa.Column('content_format', postgresql.ENUM('plain', 'markdown', name='text_format', create_type=False), nullable=False, server_default='markdown'))
    op.add_column('question_options', sa.Column('explanation', sa.Text(), nullable=True))
    # Populate from the 'en' translation (or any single translation) where possible.
    op.execute("""
    UPDATE questions q SET stem = t.stem, stem_format = t.stem_format, language = t.language
      FROM question_translations t WHERE t.question_id = q.id AND t.language = 'en';
    INSERT INTO explanations (question_id, correct_answer_rationale, key_point_summary, further_reading)
    SELECT question_id, correct_answer_rationale, key_point_summary, further_reading
      FROM question_translations WHERE language = 'en'
    ON CONFLICT DO NOTHING;
    """)
    op.drop_constraint('uq_qek_dataset_ext', 'question_external_keys', type_='unique')
    op.alter_column('question_external_keys', 'language', existing_type=sa.String(length=5), nullable=False)
    op.create_unique_constraint('uq_qek_dataset_ext_lang', 'question_external_keys', ['dataset_slug', 'external_id', 'language'])
    op.drop_column('users', 'language_mode')
    op.drop_index('ix_questions_available_languages', table_name='questions')
    op.drop_column('questions', 'available_languages')
    op.drop_table('question_translations')
