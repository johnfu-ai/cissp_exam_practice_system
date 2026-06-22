import uuid

import pytest

from app.models.enums import QuestionStatus, QuestionType
from app.models.question import (
    QuestionMapping,
    QuestionOption,
    QuestionRevision,
)
from app.schemas.question import (
    ExplanationIn,
    MappingsIn,
    OptionIn,
    QuestionCreateIn,
)
from app.services.question import ValidationError, create_question


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


def _single_payload(**kw):
    return QuestionCreateIn(
        question_type=QuestionType.single_choice,
        stem="What is 1+1?",
        options=[
            OptionIn(content="2", is_correct=True, order_index=0),
            OptionIn(content="3", is_correct=False, order_index=1),
        ],
        explanation=ExplanationIn(correct_answer_rationale="2"),
        **kw,
    )


def test_create_single_choice(db_session):
    org = _org(db_session)
    actor = _actor(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=actor, payload=_single_payload())
    assert q.id is not None
    assert q.status == QuestionStatus.draft
    assert q.version == 1
    assert q.organization_id == org.id
    opts = db_session.query(QuestionOption).filter_by(question_id=q.id).all()
    assert len(opts) == 2
    assert sum(o.is_correct for o in opts) == 1
    revs = db_session.query(QuestionRevision).filter_by(question_id=q.id).all()
    assert len(revs) == 1
    assert revs[0].revision_number == 1


def test_create_writes_explanation_and_mappings(db_session):
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
    from app.models.question import Explanation
    assert db_session.query(Explanation).filter_by(question_id=q.id).one().correct_answer_rationale == "2"


def test_create_multiple_choice_requires_two_correct(db_session):
    org = _org(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.multiple_choice, stem="pick two",
        options=[
            OptionIn(content="a", is_correct=True, order_index=0),
            OptionIn(content="b", is_correct=False, order_index=1),
        ],
    )
    with pytest.raises(ValidationError):
        create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=payload)


def test_create_single_choice_exactly_one_correct(db_session):
    org = _org(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice, stem="x",
        options=[
            OptionIn(content="a", is_correct=False, order_index=0),
            OptionIn(content="b", is_correct=False, order_index=1),
        ],
    )
    with pytest.raises(ValidationError):
        create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=payload)


def test_create_true_false_two_options_one_correct(db_session):
    org = _org(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.true_false, stem="sky is blue",
        options=[
            OptionIn(content="True", is_correct=True, order_index=0),
            OptionIn(content="False", is_correct=False, order_index=1),
            OptionIn(content="Maybe", is_correct=False, order_index=2),
        ],
    )
    with pytest.raises(ValidationError):
        create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=payload)


def test_create_option_count_bounds(db_session):
    org = _org(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice, stem="x",
        options=[OptionIn(content="only", is_correct=True, order_index=0)],
    )
    with pytest.raises(ValidationError):
        create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=payload)


def test_create_empty_stem_rejected(db_session):
    org = _org(db_session)
    payload = QuestionCreateIn(
        question_type=QuestionType.single_choice, stem="   ",
        options=[
            OptionIn(content="a", is_correct=True, order_index=0),
            OptionIn(content="b", is_correct=False, order_index=1),
        ],
    )
    with pytest.raises(ValidationError):
        create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=payload)


# --- Task 5: get + list ---

from app.services.question import get_question, list_questions, NotFound  # noqa: E402


def test_get_question_missing_raises(db_session):
    with pytest.raises(NotFound):
        get_question(db_session, uuid.uuid4())


def test_get_question_excludes_soft_deleted(db_session):
    from datetime import datetime, timezone

    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session),
                        payload=_single_payload())
    q.deleted_at = datetime.now(timezone.utc)
    db_session.flush()
    with pytest.raises(NotFound):
        get_question(db_session, q.id)


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


def test_list_search_by_stem(db_session):
    org = _org(db_session)
    create_question(db_session, org_id=org.id, actor_id=_actor(db_session),
                    payload=QuestionCreateIn(
                        question_type=QuestionType.single_choice, stem="Cryptography basics",
                        options=[OptionIn(content="a", is_correct=True, order_index=0),
                                 OptionIn(content="b", order_index=1)]))
    _, total = list_questions(db_session, org_id=org.id, page=1, size=20,
                              filters={"search": "crypto"})
    assert total == 1


# --- Task 6: update + revisions ---

from app.schemas.question import QuestionUpdateIn  # noqa: E402
from app.services.question import list_revisions, update_question  # noqa: E402


def test_update_bumps_version_and_writes_revision(db_session):
    org = _org(db_session)
    actor = _actor(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=actor, payload=_single_payload())
    updated = update_question(db_session, question_id=q.id, actor_id=actor,
                              payload=QuestionUpdateIn(stem="What is 2+2?"))
    assert updated.version == 2
    assert updated.stem == "What is 2+2?"
    revs = list_revisions(db_session, q.id)
    assert len(revs) == 2
    # pre-edit revision (revision #2) captures the ORIGINAL stem before this edit
    assert revs[1].snapshot["stem"] == "What is 1+1?"


def test_update_options_revalidates(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    with pytest.raises(ValidationError):
        update_question(db_session, question_id=q.id, actor_id=_actor(db_session),
                        payload=QuestionUpdateIn(options=[
                            OptionIn(content="a", is_correct=False, order_index=0),
                            OptionIn(content="b", is_correct=False, order_index=1),
                        ]))


def test_update_noop_does_not_bump(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    updated = update_question(db_session, question_id=q.id, actor_id=_actor(db_session),
                              payload=QuestionUpdateIn())
    assert updated.version == 1


# --- Task 7: soft delete ---

from app.services.question import delete_question  # noqa: E402


def test_soft_delete_excludes_from_list(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    delete_question(db_session, question_id=q.id, actor_id=_actor(db_session))
    items, total = list_questions(db_session, org_id=org.id, page=1, size=20)
    assert total == 0
    assert items == []
    with pytest.raises(NotFound):
        get_question(db_session, q.id)


# --- Task 8: review state machine ---

from app.schemas.question import ReviewAction  # noqa: E402
from app.services.question import IllegalTransition, submit_review  # noqa: E402


def test_review_draft_to_published(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    q = submit_review(db_session, question_id=q.id, actor_id=_actor(db_session),
                      action=ReviewAction.submit)
    assert q.status == QuestionStatus.pending_review
    q = submit_review(db_session, question_id=q.id, actor_id=_actor(db_session),
                      action=ReviewAction.approve)
    assert q.status == QuestionStatus.published


def test_review_request_changes(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    submit_review(db_session, question_id=q.id, actor_id=_actor(db_session), action=ReviewAction.submit)
    q = submit_review(db_session, question_id=q.id, actor_id=_actor(db_session),
                      action=ReviewAction.request_changes)
    assert q.status == QuestionStatus.needs_revision
    q = submit_review(db_session, question_id=q.id, actor_id=_actor(db_session),
                      action=ReviewAction.submit)
    assert q.status == QuestionStatus.pending_review


def test_review_archive_and_restore(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    q = submit_review(db_session, question_id=q.id, actor_id=_actor(db_session),
                      action=ReviewAction.archive)
    assert q.status == QuestionStatus.archived
    q = submit_review(db_session, question_id=q.id, actor_id=_actor(db_session),
                      action=ReviewAction.restore)
    assert q.status == QuestionStatus.draft


def test_review_illegal_transition(db_session):
    org = _org(db_session)
    q = create_question(db_session, org_id=org.id, actor_id=_actor(db_session), payload=_single_payload())
    with pytest.raises(IllegalTransition):
        submit_review(db_session, question_id=q.id, actor_id=_actor(db_session),
                      action=ReviewAction.approve)
