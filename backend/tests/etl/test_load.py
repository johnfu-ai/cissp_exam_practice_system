"""ETL Load tests: one Question + N translations per external_id."""

from datetime import date

from sqlalchemy import func, select

from app.etl.load import LoadResult, apply_dry_run, apply_load
from app.etl.transform import CleanedOption, CleanedQuestion
from app.models.enums import QuestionType
from app.models.etl import ChapterDomainMapping, QuestionExternalKey
from app.models.question import (
    Question,
    QuestionMapping,
    QuestionOption,
    QuestionRevision,
    QuestionTranslation,
)
from app.models.taxonomy import ExamBlueprint, ExamDomain


def _cleaned_bilingual(external_id="c1", stem_en="Stem", stem_zh="题干",
                       explanation_en="Exp", explanation_zh="解析", correct=("A",)):
    return CleanedQuestion(
        external_id=external_id,
        question_type=QuestionType.single_choice,
        stem_en=stem_en,
        stem_zh=stem_zh,
        options=[CleanedOption(key="A", text_en="A", text_zh="甲", is_correct="A" in correct),
                 CleanedOption(key="B", text_en="B", text_zh="乙", is_correct="B" in correct)],
        explanation_en=explanation_en,
        explanation_zh=explanation_zh,
        prompt_items=None,
        source_chapter=1,
        source_chapter_title="Chapter One",
        difficulty=3,
        issues=[],
        needs_revision=False,
        available_languages=["en", "zh"],
    )


def _cleaned_en_only(external_id="c2", stem_en="Stem"):
    return CleanedQuestion(
        external_id=external_id,
        question_type=QuestionType.single_choice,
        stem_en=stem_en,
        stem_zh="",
        options=[CleanedOption(key="A", text_en="A", text_zh="", is_correct=True),
                 CleanedOption(key="B", text_en="B", text_zh="", is_correct=False)],
        explanation_en="Exp",
        explanation_zh="",
        prompt_items=None,
        source_chapter=1,
        source_chapter_title="Chapter One",
        difficulty=3,
        issues=["missing_zh"],
        needs_revision=True,
        available_languages=["en"],
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


def _count(session, model):
    return session.execute(select(func.count()).select_from(model)).scalar_one()


def test_load_writes_one_question_with_two_translations(db_session):
    org_id = _seed_org_and_domain(db_session)
    cleaned = _cleaned_bilingual()
    result = apply_load(db_session, org_id, "osg10", None, [cleaned])
    assert result.created == 1
    assert result.updated == 0
    assert result.unchanged == 0

    qs = db_session.execute(select(Question).filter_by(deleted_at=None)).scalars().all()
    assert len(qs) == 1
    assert qs[0].available_languages == ["en", "zh"]
    assert qs[0].status.value == "draft"
    assert qs[0].source == "c1"

    ts = db_session.execute(select(QuestionTranslation).where(
        QuestionTranslation.question_id == qs[0].id)).scalars().all()
    assert {t.language for t in ts} == {"en", "zh"}

    # exactly one external key per external_id (no per-language fan-out)
    keys = db_session.execute(select(QuestionExternalKey).filter_by(
        external_id=cleaned.external_id)).scalars().all()
    assert len(keys) == 1
    assert keys[0].question_id == qs[0].id
    assert keys[0].language == "en"  # first available language

    # canonical options carry only order_index + is_correct (no content)
    opts = db_session.execute(select(QuestionOption).where(
        QuestionOption.question_id == qs[0].id).order_by(QuestionOption.order_index)).scalars().all()
    assert len(opts) == 2
    assert [o.is_correct for o in opts] == [True, False]

    # translation rows carry localized content
    en_t = next(t for t in ts if t.language == "en")
    assert en_t.stem == "Stem"
    assert en_t.correct_answer_rationale == "Exp"
    assert en_t.options[0]["content"] == "A"
    assert en_t.options[0]["content_format"] == "markdown"
    assert en_t.options[0]["explanation"] is None
    zh_t = next(t for t in ts if t.language == "zh")
    assert zh_t.stem == "题干"
    assert zh_t.options[0]["content"] == "甲"

    # mapping has domain_id resolved from ChapterDomainMapping
    mapping = db_session.execute(select(QuestionMapping)).scalar_one()
    assert mapping.domain_id is not None


def test_load_en_only_writes_one_question_one_translation(db_session):
    org_id = _seed_org_and_domain(db_session)
    cleaned = _cleaned_en_only()
    result = apply_load(db_session, org_id, "osg10", None, [cleaned])
    assert result.created == 1

    q = db_session.execute(select(Question).filter_by(deleted_at=None)).scalar_one()
    assert q.available_languages == ["en"]
    assert q.status.value == "needs_revision"

    ts = db_session.execute(select(QuestionTranslation).where(
        QuestionTranslation.question_id == q.id)).scalars().all()
    assert {t.language for t in ts} == {"en"}

    keys = db_session.execute(select(QuestionExternalKey)).scalars().all()
    assert len(keys) == 1
    assert keys[0].language == "en"


def test_load_idempotent_on_external_id(db_session):
    org_id = _seed_org_and_domain(db_session)
    cleaned = _cleaned_bilingual()
    apply_load(db_session, org_id, "osg10", None, [cleaned])
    result = apply_load(db_session, org_id, "osg10", None, [cleaned])  # unchanged
    assert result.unchanged == 1
    assert result.created == 0
    assert result.updated == 0

    assert _count(db_session, Question) == 1
    assert _count(db_session, QuestionExternalKey) == 1
    assert _count(db_session, QuestionTranslation) == 2
    assert _count(db_session, QuestionRevision) == 0


def test_load_update_writes_revision_and_bumps_version(db_session):
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual(stem_en="Old")])
    result = apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual(stem_en="New")])
    assert result.updated == 1

    q = db_session.execute(select(Question).filter_by(deleted_at=None)).scalar_one()
    assert q.version == 2

    rev = db_session.execute(select(QuestionRevision)).scalar_one()
    # pre-edit snapshot captured the en translation stem
    assert rev.snapshot["translations"]["en"]["stem"] == "Old"
    assert rev.revision_number == 1  # old version before bump

    # new en translation reflects updated stem
    en_t = db_session.execute(select(QuestionTranslation).filter_by(
        language="en", question_id=q.id)).scalar_one()
    assert en_t.stem == "New"


def test_load_update_replaces_options_and_translations_without_duplication(db_session):
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual(correct=("A",))])
    # flip correctness to B -> differs
    result = apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual(correct=("B",))])
    assert result.updated == 1

    q = db_session.execute(select(Question).filter_by(deleted_at=None)).scalar_one()
    opts = db_session.execute(select(QuestionOption).where(
        QuestionOption.question_id == q.id).order_by(QuestionOption.order_index)).scalars().all()
    assert [o.is_correct for o in opts] == [False, True]
    # still exactly two translations (en + zh), not duplicated
    assert _count(db_session, QuestionTranslation) == 2
    assert _count(db_session, QuestionOption) == 2


def test_load_error_isolation_records_language_none(db_session):
    org_id = _seed_org_and_domain(db_session)
    good = _cleaned_bilingual()
    # malformed: en stem None violates NOT NULL on QuestionTranslation.stem
    bad = CleanedQuestion(
        external_id="bad", question_type=QuestionType.single_choice,
        stem_en=None, stem_zh=None,
        options=[CleanedOption(key="A", text_en="A", text_zh="甲", is_correct=True)],
        explanation_en="e", explanation_zh="e", prompt_items=None, source_chapter=1,
        source_chapter_title="C", difficulty=3, issues=[], needs_revision=False,
        available_languages=["en", "zh"],
    )
    result = apply_load(db_session, org_id, "osg10", None, [good, bad])
    assert result.created == 1  # good one survived
    assert len(result.errors) == 1
    assert result.errors[0]["external_id"] == "bad"
    assert result.errors[0]["language"] is None


def test_apply_dry_run_classifies_without_writing(db_session):
    org_id = _seed_org_and_domain(db_session)
    summary = apply_dry_run(db_session, org_id, "osg10", [_cleaned_bilingual()])
    assert summary.would_create == 1
    assert summary.would_update == 0
    assert summary.unchanged == 0
    # bilingual record increments both en and zh
    assert summary.by_language == {"en": 1, "zh": 1}
    assert summary.by_type == {"single_choice": 1}
    assert _count(db_session, Question) == 0


def test_apply_dry_run_detects_existing_unchanged(db_session):
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual()])
    summary = apply_dry_run(db_session, org_id, "osg10", [_cleaned_bilingual()])
    assert summary.would_create == 0
    assert summary.would_update == 0
    assert summary.unchanged == 1


def test_load_supplements_zh_translation_on_reimport(db_session):
    """FR-LANG-08: re-importing an en-only question with zh content updates it
    to bilingual (writes the zh translation, sets available_languages, clears
    needs_revision -> draft). en stem + answer key are unchanged so the only
    signal is the language-coverage change.
    """
    org_id = _seed_org_and_domain(db_session)

    # 1. en-only -> one Question, one en translation, needs_revision
    result = apply_load(db_session, org_id, "osg10", None, [_cleaned_en_only(external_id="sup1")])
    assert result.created == 1
    q = db_session.execute(select(Question).filter_by(deleted_at=None)).scalar_one()
    assert q.available_languages == ["en"]
    assert q.status.value == "needs_revision"
    assert _count(db_session, QuestionTranslation) == 1

    # 2. same external_id, now bilingual -> _differs True -> update path runs
    result = apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual(external_id="sup1")])
    assert result.updated == 1
    assert result.unchanged == 0

    # 3. final state: 1 Question, 2 translations, bilingual, draft
    assert _count(db_session, Question) == 1
    assert _count(db_session, QuestionTranslation) == 2
    q = db_session.execute(select(Question).filter_by(deleted_at=None)).scalar_one()
    assert q.available_languages == ["en", "zh"]
    assert q.status.value == "draft"
    ts = db_session.execute(select(QuestionTranslation).where(
        QuestionTranslation.question_id == q.id)).scalars().all()
    assert {t.language for t in ts} == {"en", "zh"}
    zh_t = next(t for t in ts if t.language == "zh")
    assert zh_t.stem == "题干"


def test_load_update_detects_en_option_content_change(db_session):
    """Regression: re-importing with only an English option text edit must be
    classified 'updated' (not 'unchanged'), bump the version, and write a
    revision. Before B1, _differs omitted option-content comparison and the
    change was silently dropped (stale content retained, no version bump).
    """
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual()])
    # edit ONLY the English content of option A ("A" -> "AAA"); answer key, stem,
    # rationale, question_type, and language coverage are all unchanged.
    edited = _cleaned_bilingual()
    edited.options[0] = CleanedOption(
        key="A", text_en="AAA", text_zh="甲", is_correct=True,
    )
    edited.options[1] = CleanedOption(
        key="B", text_en="B", text_zh="乙", is_correct=False,
    )
    result = apply_load(db_session, org_id, "osg10", None, [edited])
    assert result.updated == 1
    assert result.unchanged == 0

    q = db_session.execute(select(Question).filter_by(deleted_at=None)).scalar_one()
    assert q.version == 2
    # a pre-edit revision snapshot was written
    rev = db_session.execute(select(QuestionRevision)).scalar_one()
    assert rev.snapshot["translations"]["en"]["options"][0]["content"] == "A"
    # the live en translation reflects the edited option text
    en_t = db_session.execute(select(QuestionTranslation).filter_by(
        language="en", question_id=q.id)).scalar_one()
    assert en_t.options[0]["content"] == "AAA"


def test_load_update_detects_question_type_change(db_session):
    """Regression: a question_type change alone must be detected as 'updated'."""
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual()])
    edited = _cleaned_bilingual()
    edited.question_type = QuestionType.multiple_choice
    # multiple_choice requires >=2 correct keys; flip B correct so the cleaned
    # record is valid and the only structural signal is the type change.
    edited.options[1] = CleanedOption(
        key="B", text_en="B", text_zh="乙", is_correct=True,
    )
    result = apply_load(db_session, org_id, "osg10", None, [edited])
    assert result.updated == 1
    assert result.unchanged == 0

    q = db_session.execute(select(Question).filter_by(deleted_at=None)).scalar_one()
    assert q.question_type == QuestionType.multiple_choice
    assert q.version == 2


def test_load_update_detects_en_rationale_change(db_session):
    """A correct_answer_rationale edit alone must be detected as 'updated'."""
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual()])
    edited = _cleaned_bilingual(explanation_en="New explanation")
    result = apply_load(db_session, org_id, "osg10", None, [edited])
    assert result.updated == 1
    assert result.unchanged == 0
    q = db_session.execute(select(Question).filter_by(deleted_at=None)).scalar_one()
    en_t = db_session.execute(select(QuestionTranslation).filter_by(
        language="en", question_id=q.id)).scalar_one()
    assert en_t.correct_answer_rationale == "New explanation"


def test_load_update_detects_zh_option_content_change(db_session):
    """A Chinese option text edit alone must be detected as 'updated'."""
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual()])
    edited = _cleaned_bilingual()
    edited.options[0] = CleanedOption(
        key="A", text_en="A", text_zh="甲甲", is_correct=True,
    )
    result = apply_load(db_session, org_id, "osg10", None, [edited])
    assert result.updated == 1
    assert result.unchanged == 0
    q = db_session.execute(select(Question).filter_by(deleted_at=None)).scalar_one()
    zh_t = db_session.execute(select(QuestionTranslation).filter_by(
        language="zh", question_id=q.id)).scalar_one()
    assert zh_t.options[0]["content"] == "甲甲"


# --- #16 / #18: difficulty + per-option explanation + license from source ---

def _cleaned_with_explanations(external_id="c1"):
    return CleanedQuestion(
        external_id=external_id,
        question_type=QuestionType.single_choice,
        stem_en="Stem", stem_zh="题干",
        options=[CleanedOption(key="A", text_en="A", text_zh="甲", is_correct=True,
                               explanation_en="A wrong", explanation_zh="A 错"),
                 CleanedOption(key="B", text_en="B", text_zh="乙", is_correct=False,
                               explanation_en="B right", explanation_zh="B 对")],
        explanation_en="Exp", explanation_zh="解析",
        prompt_items=None, source_chapter=1, source_chapter_title="Chapter One",
        difficulty=3, issues=[], needs_revision=False,
        available_languages=["en", "zh"],
    )


def test_load_writes_per_option_explanations(db_session):
    """#18: per-option explanations flow into the translation option JSON."""
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned_with_explanations()])
    q = db_session.execute(select(Question).filter_by(deleted_at=None)).scalar_one()
    en_t = db_session.execute(select(QuestionTranslation).filter_by(
        language="en", question_id=q.id)).scalar_one()
    zh_t = db_session.execute(select(QuestionTranslation).filter_by(
        language="zh", question_id=q.id)).scalar_one()
    assert en_t.options[0]["explanation"] == "A wrong"
    assert en_t.options[1]["explanation"] == "B right"
    assert zh_t.options[0]["explanation"] == "A 错"
    assert zh_t.options[1]["explanation"] == "B 对"


def test_load_empty_option_explanation_stored_as_none(db_session):
    """Absence is stored as None (not '') so delivery stays backward-compatible."""
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual()])
    q = db_session.execute(select(Question).filter_by(deleted_at=None)).scalar_one()
    en_t = db_session.execute(select(QuestionTranslation).filter_by(
        language="en", question_id=q.id)).scalar_one()
    assert en_t.options[0]["explanation"] is None


def test_load_update_detects_per_option_explanation_change(db_session):
    """#18: an added/edited per-option explanation alone triggers an update."""
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual()])  # no explanations
    result = apply_load(db_session, org_id, "osg10", None, [_cleaned_with_explanations()])
    assert result.updated == 1
    assert result.unchanged == 0
    q = db_session.execute(select(Question).filter_by(deleted_at=None)).scalar_one()
    en_t = db_session.execute(select(QuestionTranslation).filter_by(
        language="en", question_id=q.id)).scalar_one()
    assert en_t.options[0]["explanation"] == "A wrong"


def test_load_update_detects_difficulty_change(db_session):
    """#16: a difficulty change alone triggers an update (previously _differs
    ignored difficulty, so enrichment never landed)."""
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual()])  # difficulty 3
    edited = _cleaned_bilingual()
    edited.difficulty = 5
    result = apply_load(db_session, org_id, "osg10", None, [edited])
    assert result.updated == 1
    assert result.unchanged == 0
    q = db_session.execute(select(Question).filter_by(deleted_at=None)).scalar_one()
    assert q.difficulty == 5


def test_load_honors_source_license_status(db_session):
    """#18: a source-provided license_status is honored; default is unconfirmed."""
    org_id = _seed_org_and_domain(db_session)
    cleaned = _cleaned_bilingual()
    cleaned.license_status = "third_party_licensed"
    apply_load(db_session, org_id, "osg10", None, [cleaned])
    q = db_session.execute(select(Question).filter_by(deleted_at=None)).scalar_one()
    assert q.license_status.value == "third_party_licensed"


def test_load_default_license_status_unconfirmed(db_session):
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual()])
    q = db_session.execute(select(Question).filter_by(deleted_at=None)).scalar_one()
    assert q.license_status.value == "unconfirmed"


def test_load_idempotent_on_partial_zh_with_fallback(db_session):
    """A partial-zh record (zh stem present but zh options/rationale blank, so
    _write_translations falls back to en for those fields) must re-import as
    'unchanged'. A naive compare-against-text_zh would false-positive here.
    """
    org_id = _seed_org_and_domain(db_session)
    partial = CleanedQuestion(
        external_id="p1",
        question_type=QuestionType.single_choice,
        stem_en="Stem", stem_zh="题干",  # zh stem present -> zh in available_languages
        options=[CleanedOption(key="A", text_en="A", text_zh="", is_correct=True),
                 CleanedOption(key="B", text_en="B", text_zh="", is_correct=False)],
        explanation_en="Exp", explanation_zh="",  # blank -> falls back to en
        prompt_items=None, source_chapter=1, source_chapter_title="Chapter One",
        difficulty=3, issues=[], needs_revision=False,
        available_languages=["en", "zh"],
    )
    apply_load(db_session, org_id, "osg10", None, [partial])
    result = apply_load(db_session, org_id, "osg10", None, [partial])  # same -> unchanged
    assert result.unchanged == 1
    assert result.updated == 0
    assert _count(db_session, QuestionRevision) == 0


def test_load_result_dataclass_defaults():
    r = LoadResult()
    assert r.created == 0 and r.updated == 0 and r.unchanged == 0
    assert r.duplicates == 0
    assert r.errors == []
    assert r.conflicts == []


# --- Three-level dedup (FR-ETL-08 / PRD §10.4 rule 6) ---------------------
# A record imported under a NEW external_id whose stem hash OR option-set
# fingerprint matches an existing question is skipped as a duplicate and
# surfaced as a conflict for manual review (not re-created).


def _seed_two_orgs(session):
    """Two orgs sharing the GLOBAL taxonomy (blueprint/domains/chapter mappings)."""
    from app.models.auth import Organization
    from app.models.enums import OrgKind
    orgs = []
    for slug in ("t-org-a", "t-org-b"):
        org = Organization(slug=slug, name=slug.upper(), kind=OrgKind.personal)
        session.add(org)
        session.flush()
        orgs.append(org.id)
    bp = ExamBlueprint(version_label="t", effective_date=date(2024, 4, 15),
                       min_items=1, max_items=2, duration_minutes=60,
                       passing_score=700, max_score=1000, is_current=True)
    session.add(bp)
    session.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="Dom1", weight_pct=10)
    session.add(dom)
    session.flush()
    session.add(ChapterDomainMapping(dataset_slug="osg10", chapter_number=1,
                                     domain_id=dom.id, chapter_title="Chapter One"))
    session.flush()
    return orgs[0], orgs[1]


def test_load_skips_duplicate_stem_under_new_external_id(db_session):
    org_id = _seed_org_and_domain(db_session)
    # c2 reuses c1's stem ("Stem") under a new external_id -> duplicate
    result = apply_load(db_session, org_id, "osg10", None,
                        [_cleaned_bilingual(),
                         _cleaned_bilingual(external_id="c2", stem_en="Stem")])
    assert result.created == 1
    assert result.duplicates == 1
    assert len(result.conflicts) == 1
    assert result.conflicts[0]["external_id"] == "c2"
    assert result.conflicts[0]["reason"] == "duplicate_stem"
    assert _count(db_session, Question) == 1


def test_load_does_not_flag_distinct_questions_sharing_options(db_session):
    """Two questions with the SAME option set but DIFFERENT stems are distinct
    questions, not duplicates — generic option sets ({Yes, No}, {A, B, C, D}, …)
    are routinely shared across unrelated questions (several osg10 PKI scenarios
    all offer {Richard's/Sue's private/public key}). Only a stem-hash collision
    triggers a skip (PRD §10.4 rule 6); the option_set fingerprint is stored but
    not used as a skip trigger in the MVP."""
    org_id = _seed_org_and_domain(db_session)
    result = apply_load(db_session, org_id, "osg10", None, [
        _cleaned_bilingual(external_id="c1", stem_en="Original stem"),
        _cleaned_bilingual(external_id="c2", stem_en="Different stem"),  # same options A/B
    ])
    assert result.created == 2
    assert result.duplicates == 0
    assert result.conflicts == []
    assert _count(db_session, Question) == 2


def test_load_dedup_is_org_scoped(db_session):
    """A duplicate stem in a DIFFERENT org is not a duplicate — the stem-hash
    lookup is bounded by organization_id (tenant scoping)."""
    org_a, org_b = _seed_two_orgs(db_session)
    apply_load(db_session, org_a, "osg10", None, [_cleaned_bilingual(external_id="c1")])
    result = apply_load(db_session, org_b, "osg10", None, [_cleaned_bilingual(external_id="c2")])
    assert result.created == 1
    assert result.duplicates == 0
    assert _count(db_session, Question) == 2


def test_load_dedup_cross_batch_flags_earlier_import(db_session):
    """Re-importing the same stem under a new external_id in a LATER batch still
    flags the duplicate — the earlier question's hash is persisted in the DB."""
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual(external_id="c1")])
    result = apply_load(db_session, org_id, "osg10", None,
                        [_cleaned_bilingual(external_id="c2", stem_en="Stem")])
    assert result.created == 0
    assert result.duplicates == 1


def test_load_dedup_does_not_flag_same_external_id(db_session):
    """Same external_id goes through the update/unchanged path, NOT the duplicate
    path — dedup only applies to NEW external_ids."""
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual(external_id="c1")])
    result = apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual(external_id="c1")])
    assert result.unchanged == 1
    assert result.duplicates == 0
    assert result.conflicts == []


def test_dry_run_detects_within_batch_duplicates(db_session):
    """Preview must agree with commit: a within-batch duplicate is counted as
    `duplicates` (not `would_create`) so the preview doesn't over-promise."""
    org_id = _seed_org_and_domain(db_session)
    summary = apply_dry_run(db_session, org_id, "osg10", [
        _cleaned_bilingual(external_id="c1"),
        _cleaned_bilingual(external_id="c2", stem_en="Stem"),  # dup stem
    ])
    assert summary.would_create == 1
    assert summary.duplicates == 1
    assert summary.conflicts[0]["external_id"] == "c2"
    assert _count(db_session, Question) == 0  # dry-run writes nothing


def test_dry_run_detects_existing_db_duplicate(db_session):
    """Preview of a new dataset whose stem collides with an already-imported
    question flags it as a duplicate."""
    org_id = _seed_org_and_domain(db_session)
    apply_load(db_session, org_id, "osg10", None, [_cleaned_bilingual(external_id="c1")])
    summary = apply_dry_run(db_session, org_id, "osg10", [
        _cleaned_bilingual(external_id="c2", stem_en="Stem"),
    ])
    assert summary.would_create == 0
    assert summary.duplicates == 1


def test_dry_run_and_load_agree_on_duplicate_counts(db_session):
    """Consistency property: for any batch, dry-run and load classify duplicates
    identically (the preview never over- or under-counts vs. the actual commit)."""
    org_id = _seed_org_and_domain(db_session)
    batch = [
        _cleaned_bilingual(external_id="c1", stem_en="Stem A"),
        _cleaned_bilingual(external_id="c2", stem_en="Stem A"),  # dup stem
        _cleaned_bilingual(external_id="c3", stem_en="Stem B"),  # unique stem
    ]
    summary = apply_dry_run(db_session, org_id, "osg10", batch)
    result = apply_load(db_session, org_id, "osg10", None, batch)
    assert summary.would_create == result.created == 2
    assert summary.duplicates == result.duplicates == 1
    assert [c["external_id"] for c in summary.conflicts] == ["c2"]
    assert [c["external_id"] for c in result.conflicts] == ["c2"]
