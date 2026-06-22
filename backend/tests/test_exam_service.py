"""Service-layer tests for fixed exam API (sub-project F)."""

import pytest

from app.models.auth import Organization, User
from app.models.enums import (
    OrgKind,
    QuestionStatus,
    QuestionType,
    TextFormat,
)
from app.models.exam import ExamSession
from app.models.question import Question, QuestionOption
from app.services import exam as svc


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


def _question(db_session, org, actor, *, stem="q",
              qtype=QuestionType.single_choice, options=None):
    q = Question(
        organization_id=org.id,
        question_type=qtype,
        stem=stem,
        stem_format=TextFormat.markdown,
        status=QuestionStatus.published,
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


def test_exam_session_has_config_column(db_session):
    """ExamSession must expose a config JSONB column (default '{}')."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    from app.models.enums import ExamSessionKind
    from app.models.taxonomy import ExamBlueprint

    bp = ExamBlueprint(
        version_label="v1", effective_date="2026-04-15",
        min_items=1, max_items=10, duration_minutes=30,
        passing_score=700, max_score=1000, is_current=True,
    )
    db_session.add(bp)
    db_session.flush()
    es = ExamSession(
        user_id=actor.id, organization_id=org.id, blueprint_id=bp.id,
        session_kind=ExamSessionKind.fixed, total_questions=0,
    )
    db_session.add(es)
    db_session.flush()
    assert es.config is not None
