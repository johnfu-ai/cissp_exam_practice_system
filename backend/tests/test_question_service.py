"""Question service tests: translations-based CRUD, lifecycle, revisions, feedback.

Question content (stem, options, rationale) lives in per-language
``QuestionTranslation`` rows; the canonical ``QuestionOption`` carries only the
answer key (order_index + is_correct). ``Question.available_languages`` is
derived from the translation rows.
"""

import uuid

import pytest

from app.models.enums import QuestionStatus, QuestionType
from app.models.question import (
    QuestionMapping,
    QuestionOption,
    QuestionRevision,
    QuestionTranslation,
)
from app.schemas.question import (
    MappingsIn,
    OptionIn,
    QuestionCreateIn,
    QuestionUpdateIn,
    ReviewAction,
    TranslationIn,
    TranslationOptionIn,
)
from app.services.question import (
    IllegalTransition,
    NotFound,
    ValidationError,
    create_feedback,
    create_question,
    delete_question,
    get_question,
    get_translations,
    list_feedback,
    list_questions,
    list_revisions,
    submit_review,
    update_question,
)


# --- fixtures / helpers ------------------------------------------------------


def _org(db_session):
    from app.models.auth import Organization
    from app.models.enums import OrgKind

    org = Organization(slug=f"q-org-{uuid.uuid4().hex[:6]}", name="Q", kind=OrgKind.personal)
    db_session.add(org)
    db_session.flush()
    return org


def _actor(db_session):
    """Create a real User row (questions.created_by_id is FK-constrained)."""
    from app.models.auth import User

    user = User(email=f"actor-{uuid.uuid4().hex[:8]}@example.com")
    db_session.add(user)
    db_session.flush()
    return user.id


def _trans(language="en", stem="What is 1+1?", rationale="Because 1+1=2.",
           options=None):
    return TranslationIn(
        language=language,
        stem=stem,
        correct_answer_rationale=rationale,
        options=options
        if options is not None
        else [
            TranslationOptionIn(order_index=0, content="2"),
            TranslationOptionIn(order_index=1, content="3"),
        ],
    )


def _single_payload(**kw):
    translations = kw.pop("translations", [_trans()])
    return QuestionCreateIn(
        question_type=QuestionType.single_choice,
        options=[
            OptionIn(order_index=0, is_correct=True),
            OptionIn(order_index=1, is_correct=False),
        ],
        translations=translations,
        **kw,
    )


# --- create ------------------------------------------------------------------


def test_create_single_choice(db_session):
    org = _org(db_session)
    actor = _actor(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=actor, payload=_single_payload())
    assert q.id is not None
    assert q.status == QuestionStatus.draft
    assert q.version == 1
    assert q.organization_id == org.id
    assert q.available_languages == ["en"]
    opts = db_session.query(QuestionOption).filter_by(question_id=q.id).all()
    assert len(opts) == 2
    assert sum(o.is_correct for o in opts) == 1
    trans = get_translations(db_session, q.id)
    assert len(trans) == 1
    assert trans[0].language == "en"
    assert trans[0].stem == "What is 1+1?"
    revs = db_session.query(QuestionRevision).filter_by(question_id=q.id).all()
    assert len(revs) == 1
    assert revs[0].revision_number == 1


def test_create_question_with_translations_sets_available_languages(db_session):
    org = _org(db_session)
    actor = _actor(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice,
        options=[
            OptionIn(order_index=0, is_correct=True),
            OptionIn(order_index=1, is_correct=False),
        ],
        translations=[
            _trans("en", stem="en?", rationale="en r"),
            _trans("zh", stem="中?", rationale="中r",
                   options=[TranslationOptionIn(order_index=0, content="甲"),
                            TranslationOptionIn(order_index=1, content="乙")]),
        ],
    )
    q = create_question(db_session, org_id=org.id, actor_id=actor, payload=payload)
    assert q.available_languages == ["en", "zh"]
    assert len(get_translations(db_session, q.id)) == 2


def test_create_writes_translations_and_mappings(db_session):
    from app.models.taxonomy import ExamBlueprint, ExamDomain, KnowledgePoint, Tag

    org = _org(db_session)
    from datetime import date

    bp = ExamBlueprint(version_label="x", effective_date=date(2024, 4, 15),
                       min_items=1, max_items=2, duration_minutes=60,
                       passing_score=700, max_score=1000, is_current=True)
    db_session.add(bp); db_session.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=10)
    db_session.add(dom); db_session.flush()
    kp = KnowledgePoint(name="KP1"); db_session.add(kp); db_session.flush()
    tag = Tag(name="t1"); db_session.add(tag); db_session.flush()

    payload = _single_payload(mappings=MappingsIn(
        domain_id=dom.id, knowledge_point_id=kp.id, tag_ids=[tag.id]))
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=payload)
    mappings = db_session.query(QuestionMapping).filter_by(question_id=q.id).all()
    assert {m.domain_id for m in mappings if m.domain_id} == {dom.id}
    assert {m.knowledge_point_id for m in mappings if m.knowledge_point_id} == {kp.id}
    assert {m.tag_id for m in mappings if m.tag_id} == {tag.id}
    # explanation row is gone; content lives in the translation
    assert len(get_translations(db_session, q.id)) == 1


def test_create_requires_at_least_one_translation(db_session):
    org = _org(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice,
        options=[OptionIn(order_index=0, is_correct=True),
                 OptionIn(order_index=1, is_correct=False)],
        translations=[],
    )
    with pytest.raises(ValidationError):
        create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=payload)


def test_create_multiple_choice_requires_two_correct(db_session):
    org = _org(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.multiple_choice,
        options=[OptionIn(order_index=0, is_correct=True),
                 OptionIn(order_index=1, is_correct=False)],
        translations=[_trans()],
    )
    with pytest.raises(ValidationError):
        create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=payload)


def test_create_single_choice_exactly_one_correct(db_session):
    org = _org(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice,
        options=[OptionIn(order_index=0, is_correct=False),
                 OptionIn(order_index=1, is_correct=False)],
        translations=[_trans()],
    )
    with pytest.raises(ValidationError):
        create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=payload)


def test_create_true_false_two_options_one_correct(db_session):
    org = _org(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.true_false,
        options=[OptionIn(order_index=0, is_correct=True),
                 OptionIn(order_index=1, is_correct=False),
                 OptionIn(order_index=2, is_correct=False)],
        translations=[_trans()],
    )
    with pytest.raises(ValidationError):
        create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=payload)


def test_create_option_count_bounds(db_session):
    org = _org(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice,
        options=[OptionIn(order_index=0, is_correct=True)],
        translations=[_trans(options=[TranslationOptionIn(order_index=0, content="only")])],
    )
    with pytest.raises(ValidationError):
        create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=payload)


def test_create_empty_stem_rejected(db_session):
    org = _org(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice,
        options=[OptionIn(order_index=0, is_correct=True),
                 OptionIn(order_index=1, is_correct=False)],
        translations=[_trans(stem="   ")],
    )
    with pytest.raises(ValidationError):
        create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=payload)


# --- get + list --------------------------------------------------------------


def test_get_question_missing_raises(db_session):
    with pytest.raises(NotFound):
        get_question(db_session, uuid.uuid4(), org_id=uuid.uuid4())


def test_get_question_excludes_soft_deleted(db_session):
    from datetime import datetime, timezone

    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session),
                        payload=_single_payload())
    q.deleted_at = datetime.now(timezone.utc)
    db_session.flush()
    with pytest.raises(NotFound):
        get_question(db_session, q.id, org_id=org.id)


def test_list_pagination_and_tenant(db_session):
    org = _org(db_session)
    other = _org(db_session)
    for _ in range(3):
        create_question(db_session, org_id=org.id, actor_id=_actor(db_session),
                        payload=_single_payload())
    create_question(db_session, org_id=other.id, actor_id=_actor(db_session),
                    payload=_single_payload())
    items, total = list_questions(db_session, org_id=org.id, page=1, size=2)
    assert total == 3
    assert len(items) == 2
    items2, _ = list_questions(db_session, org_id=org.id, page=2, size=2)
    assert len(items2) == 1


def test_list_filter_by_status(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session),
                        payload=_single_payload())
    q.status = QuestionStatus.published
    db_session.flush()
    _, total = list_questions(db_session, org_id=org.id, page=1, size=20,
                              filters={"status": QuestionStatus.published})
    assert total == 1
    _, total_draft = list_questions(db_session, org_id=org.id, page=1, size=20,
                                    filters={"status": QuestionStatus.draft})
    assert total_draft == 0


def test_list_search_by_translation_stem(db_session):
    org = _org(db_session)
    create_question(db_session, org_id=org.id, actor_id=_actor(db_session),
                    payload=_single_payload(translations=[_trans(stem="Cryptography basics")]))
    create_question(db_session, org_id=org.id, actor_id=_actor(db_session),
                    payload=_single_payload(translations=[_trans(stem="Networking basics")]))
    _, total = list_questions(db_session, org_id=org.id, page=1, size=20,
                              filters={"search": "crypto"})
    assert total == 1


def test_list_questions_missing_language_zh(db_session):
    org = _org(db_session)
    # en-only question
    create_question(db_session, org_id=org.id, actor_id=_actor(db_session),
                    payload=_single_payload(translations=[_trans("en")]))
    # bilingual question
    create_question(db_session, org_id=org.id, actor_id=_actor(db_session),
                    payload=_single_payload(translations=[
                        _trans("en", stem="en?"),
                        _trans("zh", stem="中?",
                               options=[TranslationOptionIn(order_index=0, content="甲"),
                                        TranslationOptionIn(order_index=1, content="乙")]),
                    ]))
    items, total = list_questions(db_session, org_id=org.id, page=1, size=20,
                                  filters={"missing_language": "zh"})
    assert total == 1
    assert items[0].available_languages == ["en"]


# --- update + revisions ------------------------------------------------------


def test_update_bumps_version_and_writes_revision(db_session):
    org = _org(db_session)
    actor = _actor(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=actor, payload=_single_payload())
    updated = update_question(db_session, question_id=q.id, actor_id=actor, org_id=org.id,
                              payload=QuestionUpdateIn(translations=[_trans(stem="What is 2+2?")]))
    assert updated.version == 2
    assert updated.available_languages == ["en"]
    revs = list_revisions(db_session, q.id)
    assert len(revs) == 2
    # pre-edit revision (revision #2) captures the ORIGINAL stem before this edit
    assert revs[1].snapshot["translations"]["en"]["stem"] == "What is 1+1?"


def test_update_options_revalidates(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    with pytest.raises(ValidationError):
        update_question(db_session, question_id=q.id, actor_id=_actor(db_session), org_id=org.id,
                        payload=QuestionUpdateIn(options=[
                            OptionIn(order_index=0, is_correct=False),
                            OptionIn(order_index=1, is_correct=False),
                        ]))


def test_update_replaces_translations(db_session):
    org = _org(db_session)
    actor = _actor(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=actor,
                        payload=_single_payload(translations=[_trans("en")]))
    assert q.available_languages == ["en"]
    # Replace en-only with zh-only (translations are replaced, not appended)
    update_question(db_session, question_id=q.id, actor_id=actor, org_id=org.id,
                    payload=QuestionUpdateIn(translations=[
                        _trans("zh", stem="中?", rationale="中r",
                               options=[TranslationOptionIn(order_index=0, content="甲"),
                                        TranslationOptionIn(order_index=1, content="乙")]),
                    ]))
    db_session.refresh(q)
    assert q.available_languages == ["zh"]
    trans = get_translations(db_session, q.id)
    assert len(trans) == 1
    assert trans[0].language == "zh"


def test_update_adds_bilingual_translations(db_session):
    org = _org(db_session)
    actor = _actor(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=actor,
                        payload=_single_payload(translations=[_trans("en")]))
    update_question(db_session, question_id=q.id, actor_id=actor, org_id=org.id,
                    payload=QuestionUpdateIn(translations=[
                        _trans("en", stem="en?"),
                        _trans("zh", stem="中?",
                               options=[TranslationOptionIn(order_index=0, content="甲"),
                                        TranslationOptionIn(order_index=1, content="乙")]),
                    ]))
    db_session.refresh(q)
    assert q.available_languages == ["en", "zh"]
    assert len(get_translations(db_session, q.id)) == 2


def test_update_noop_does_not_bump(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    updated = update_question(db_session, question_id=q.id, actor_id=_actor(db_session), org_id=org.id,
                              payload=QuestionUpdateIn())
    assert updated.version == 1


# --- soft delete -------------------------------------------------------------


def test_soft_delete_excludes_from_list(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    delete_question(db_session, question_id=q.id, actor_id=_actor(db_session), org_id=org.id)
    items, total = list_questions(db_session, org_id=org.id, page=1, size=20)
    assert total == 0
    assert items == []
    with pytest.raises(NotFound):
        get_question(db_session, q.id, org_id=org.id)


# --- review state machine ----------------------------------------------------


def test_review_draft_to_published(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    q = submit_review(db_session, question_id=q.id, actor_id=_actor(db_session),
                      action=ReviewAction.submit, org_id=org.id)
    assert q.status == QuestionStatus.pending_review
    q = submit_review(db_session, question_id=q.id, actor_id=_actor(db_session),
                      action=ReviewAction.approve, org_id=org.id)
    assert q.status == QuestionStatus.published


def test_review_request_changes(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    submit_review(db_session, question_id=q.id, actor_id=_actor(db_session), action=ReviewAction.submit, org_id=org.id)
    q = submit_review(db_session, question_id=q.id, actor_id=_actor(db_session),
                      action=ReviewAction.request_changes, org_id=org.id)
    assert q.status == QuestionStatus.needs_revision
    q = submit_review(db_session, question_id=q.id, actor_id=_actor(db_session),
                      action=ReviewAction.submit, org_id=org.id)
    assert q.status == QuestionStatus.pending_review


def test_review_archive_and_restore(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    q = submit_review(db_session, question_id=q.id, actor_id=_actor(db_session),
                      action=ReviewAction.archive, org_id=org.id)
    assert q.status == QuestionStatus.archived
    q = submit_review(db_session, question_id=q.id, actor_id=_actor(db_session),
                      action=ReviewAction.restore, org_id=org.id)
    assert q.status == QuestionStatus.draft


def test_review_illegal_transition(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    with pytest.raises(IllegalTransition):
        submit_review(db_session, question_id=q.id, actor_id=_actor(db_session),
                      action=ReviewAction.approve, org_id=org.id)


# --- publish validation (FR-LANG-09) ----------------------------------------


def test_publish_requires_complete_translations(db_session):
    """A question whose zh translation is present but incomplete must NOT be
    approvable (FR-LANG-09: present translations must all be complete)."""
    org = _org(db_session)
    actor = _actor(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=actor,
                        payload=_single_payload(translations=[
                            _trans("en", stem="en?", rationale="en r"),
                            _trans("zh", stem="中?", rationale="中r",
                                   options=[TranslationOptionIn(order_index=0, content="甲"),
                                            TranslationOptionIn(order_index=1, content="乙")]),
                        ]))
    submit_review(db_session, question_id=q.id, actor_id=actor, action=ReviewAction.submit, org_id=org.id)
    # Make zh incomplete: blank the rationale.
    zh = db_session.query(QuestionTranslation).filter_by(
        question_id=q.id, language="zh").one()
    zh.correct_answer_rationale = ""
    db_session.flush()
    with pytest.raises(ValidationError):
        submit_review(db_session, question_id=q.id, actor_id=actor, action=ReviewAction.approve, org_id=org.id)


def test_publish_blocks_when_no_complete_translation(db_session):
    """If no translation is complete, approve fails with the no-complete rule."""
    org = _org(db_session)
    actor = _actor(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=actor,
                        payload=_single_payload(translations=[_trans("en")]))
    submit_review(db_session, question_id=q.id, actor_id=actor, action=ReviewAction.submit, org_id=org.id)
    # Blank the only translation's rationale -> no complete translation.
    en = db_session.query(QuestionTranslation).filter_by(
        question_id=q.id, language="en").one()
    en.correct_answer_rationale = ""
    db_session.flush()
    with pytest.raises(ValidationError):
        submit_review(db_session, question_id=q.id, actor_id=actor, action=ReviewAction.approve, org_id=org.id)


def test_publish_allows_bilingual_when_both_complete(db_session):
    org = _org(db_session)
    actor = _actor(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=actor,
                        payload=_single_payload(translations=[
                            _trans("en", stem="en?", rationale="en r"),
                            _trans("zh", stem="中?", rationale="中r",
                                   options=[TranslationOptionIn(order_index=0, content="甲"),
                                            TranslationOptionIn(order_index=1, content="乙")]),
                        ]))
    submit_review(db_session, question_id=q.id, actor_id=actor, action=ReviewAction.submit, org_id=org.id)
    q = submit_review(db_session, question_id=q.id, actor_id=actor, action=ReviewAction.approve, org_id=org.id)
    assert q.status == QuestionStatus.published


# --- correction feedback -----------------------------------------------------


def test_create_and_list_feedback(db_session):
    from app.models.enums import QuestionFeedbackStatus, QuestionFeedbackType
    from app.schemas.question import FeedbackIn

    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    fb = create_feedback(db_session, org_id=org.id, question_id=q.id, reporter_id=_actor(db_session),
                         payload=FeedbackIn(feedback_type=QuestionFeedbackType.unclear_explanation,
                                            comment="huh?"))
    assert fb.question_id == q.id
    assert fb.status == QuestionFeedbackStatus.open
    assert len(list_feedback(db_session, question_id=q.id)) == 1


def test_create_feedback_on_deleted_question_raises(db_session):
    from app.models.enums import QuestionFeedbackType
    from app.schemas.question import FeedbackIn

    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    delete_question(db_session, question_id=q.id, actor_id=_actor(db_session), org_id=org.id)
    with pytest.raises(NotFound):
        create_feedback(db_session, org_id=org.id, question_id=q.id, reporter_id=_actor(db_session),
                        payload=FeedbackIn(feedback_type=QuestionFeedbackType.other))


# --- P0 #3: cross-tenant IDOR (org-gate) -------------------------------------

def test_get_question_cross_org_raises(db_session):
    org_a, org_b = _org(db_session), _org(db_session)
    q = create_question(db_session, org_id=org_a.id, actor_id=_actor(db_session),
                        payload=_single_payload())
    with pytest.raises(NotFound):
        get_question(db_session, q.id, org_id=org_b.id)
    # same org still resolves
    assert get_question(db_session, q.id, org_id=org_a.id).id == q.id


def test_get_question_missing_with_org_raises(db_session):
    with pytest.raises(NotFound):
        get_question(db_session, uuid.uuid4(), org_id=uuid.uuid4())


def test_update_question_cross_org_raises(db_session):
    org_a, org_b = _org(db_session), _org(db_session)
    actor = _actor(db_session)
    q = create_question(db_session, org_id=org_a.id, actor_id=actor, payload=_single_payload())
    with pytest.raises(NotFound):
        update_question(db_session, question_id=q.id, actor_id=actor,
                        org_id=org_b.id, payload=QuestionUpdateIn())


def test_delete_question_cross_org_raises(db_session):
    org_a, org_b = _org(db_session), _org(db_session)
    q = create_question(db_session, org_id=org_a.id, actor_id=_actor(db_session),
                        payload=_single_payload())
    with pytest.raises(NotFound):
        delete_question(db_session, question_id=q.id, actor_id=_actor(db_session),
                        org_id=org_b.id)
    # still present (not deleted)
    assert get_question(db_session, q.id, org_id=org_a.id).id == q.id


def test_submit_review_cross_org_raises(db_session):
    org_a, org_b = _org(db_session), _org(db_session)
    actor = _actor(db_session)
    q = create_question(db_session, org_id=org_a.id, actor_id=actor, payload=_single_payload())
    with pytest.raises(NotFound):
        submit_review(db_session, question_id=q.id, actor_id=actor,
                      action=ReviewAction.submit, org_id=org_b.id)


def test_create_feedback_cross_org_raises(db_session):
    from app.models.enums import QuestionFeedbackType
    from app.schemas.question import FeedbackIn

    org_a, org_b = _org(db_session), _org(db_session)
    q = create_question(db_session, org_id=org_a.id, actor_id=_actor(db_session),
                        payload=_single_payload())
    with pytest.raises(NotFound):
        create_feedback(db_session, org_id=org_b.id, question_id=q.id,
                        reporter_id=_actor(db_session),
                        payload=FeedbackIn(feedback_type=QuestionFeedbackType.other))
