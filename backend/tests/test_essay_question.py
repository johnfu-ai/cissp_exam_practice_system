"""Essay question type: creation + publish completeness (FR-ESSAY-01/05)."""

import pytest

from app.models.enums import QuestionType, QuestionStatus
from app.schemas.question import (
    OptionIn,
    QuestionCreateIn,
    ReviewAction,
    TranslationIn,
    TranslationOptionIn,
)
from app.core.security import InMemoryRefreshTokenStore
from app.services.auth import register_user
from app.services.errors import ValidationError
from app.services.question import create_question, submit_review


@pytest.fixture
def learner(db_session, session_with_roles):
    store = InMemoryRefreshTokenStore()
    user, _ = register_user(
        db_session, email="essay-author@example.com", password="pw12345678",
        display_name=None,
        refresh_store=store,
    )
    db_session.flush()
    return user


def _essay_payload(**overrides) -> QuestionCreateIn:
    base = dict(
        question_type=QuestionType.essay,
        options=[],
        translations=[
            TranslationIn(
                language="en",
                stem="Explain the principle of least privilege.",
                correct_answer_rationale="Reference rationale",
                options=[],
                reference_answer="Grant only the minimum access required.",
            ),
            TranslationIn(
                language="zh",
                stem="解释最小特权原则。",
                correct_answer_rationale="参考解析",
                options=[],
                reference_answer="只授予完成任务所必需的最小权限。",
            ),
        ],
    )
    base.update(overrides)
    return QuestionCreateIn(**base)


def test_essay_question_created_without_options(db_session, learner):
    q = create_question(
        db_session, org_id=learner.default_organization_id, actor_id=learner.id,
        payload=_essay_payload(),
    )
    db_session.flush()
    assert q.question_type is QuestionType.essay
    assert q.status is QuestionStatus.draft
    assert q.available_languages == ["en", "zh"]
    # reference answer persisted per language
    from app.services.question import get_translations

    trans = {t.language: t for t in get_translations(db_session, q.id)}
    assert trans["en"].reference_answer == "Grant only the minimum access required."
    assert trans["zh"].reference_answer == "只授予完成任务所必需的最小权限。"


def test_essay_rejects_options(db_session, learner):
    payload = _essay_payload(
        options=[OptionIn(order_index=0, is_correct=True)],
        translations=[
            TranslationIn(
                language="en", stem="s", correct_answer_rationale="r",
                options=[TranslationOptionIn(order_index=0, content="x")],
                reference_answer="ref",
            ),
        ],
    )
    with pytest.raises(ValidationError, match="essay"):
        create_question(
            db_session, org_id=learner.default_organization_id, actor_id=learner.id,
            payload=payload,
        )


def test_essay_publish_requires_reference_answer(db_session, learner):
    # translation without a reference answer -> cannot publish
    q = create_question(
        db_session, org_id=learner.default_organization_id, actor_id=learner.id,
        payload=_essay_payload(
            translations=[
                TranslationIn(
                    language="en", stem="Explain least privilege.",
                    correct_answer_rationale="rationale", options=[],
                    reference_answer=None,
                ),
            ],
        ),
    )
    submit_review(
        db_session, question_id=q.id, actor_id=learner.id,
        action=ReviewAction.submit, org_id=learner.default_organization_id,
    )
    with pytest.raises(ValidationError, match="reference"):
        submit_review(
            db_session, question_id=q.id, actor_id=learner.id,
            action=ReviewAction.approve, org_id=learner.default_organization_id,
        )


def test_essay_with_reference_answer_publishes(db_session, learner):
    q = create_question(
        db_session, org_id=learner.default_organization_id, actor_id=learner.id,
        payload=_essay_payload(),
    )
    org_id = learner.default_organization_id
    submit_review(db_session, question_id=q.id, actor_id=learner.id,
                  action=ReviewAction.submit, org_id=org_id)
    q = submit_review(db_session, question_id=q.id, actor_id=learner.id,
                      action=ReviewAction.approve, org_id=org_id)
    assert q.status is QuestionStatus.published
