"""Service-layer tests for practice API (sub-project E)."""

import pytest

from app.models.auth import Organization, User
from app.models.enums import (
    OrgKind,
    PracticeSessionStatus,
    QuestionStatus,
    QuestionType,
    TextFormat,
)
from app.models.practice import PracticeAnswer, PracticeSession, UserQuestionState
from app.models.question import Question, QuestionOption
from app.schemas.practice import (
    AnswerIn,
    QuestionStateIn,
    SessionCreateIn,
)
from app.services import practice as svc


def _org(db_session, slug="t"):
    org = Organization(name="T", slug=slug, kind=OrgKind.personal)
    db_session.add(org)
    db_session.flush()
    return org


def _actor(db_session, org, email="learner@example.com"):
    user = User(
        email=email,
        password_hash="x",
        display_name="L",
        default_organization_id=org.id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _question(db_session, org, actor, *, stem="q", qtype=QuestionType.single_choice,
              difficulty=None, options=None):
    q = Question(
        organization_id=org.id,
        question_type=qtype,
        stem=stem,
        stem_format=TextFormat.markdown,
        status=QuestionStatus.published,
        difficulty=difficulty,
        created_by_id=actor.id,
    )
    db_session.add(q)
    db_session.flush()
    opts = options if options is not None else [
        (0, "A", True),
        (1, "B", False),
    ]
    for order_index, content, is_correct in opts:
        db_session.add(QuestionOption(
            question_id=q.id, order_index=order_index, content=content,
            content_format=TextFormat.markdown, is_correct=is_correct,
        ))
    db_session.flush()
    return q


def test_session_has_config_and_paused_at_columns(db_session):
    """PracticeSession must expose config (JSONB) and paused_at columns."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    session = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=1),
    )
    assert session.config is not None
    assert "question_ids" in session.config
    assert session.paused_at is None
    assert session.status == PracticeSessionStatus.in_progress
