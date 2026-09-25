"""Paper / essay / wrong-book model tests (PRD v1.4 FR-PAPER/FR-ESSAY/FR-WRONG)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.enums import PaperStatus, QuestionType
from app.models.paper import Paper, PaperQuestion
from app.models.practice import UserQuestionState
from app.models.question import Question, QuestionTranslation


def _org_id(db_session) -> uuid.UUID:
    from app.models.auth import Organization, OrgKind, OrgStatus
    tag = uuid.uuid4().hex[:8]
    org = Organization(
        name=f"org-{tag}", slug=f"org-{tag}", kind=OrgKind.personal, status=OrgStatus.active
    )
    db_session.add(org)
    db_session.flush()
    return org.id


def _user_id(db_session) -> uuid.UUID:
    from app.models.auth import User, UserStatus
    user = User(
        email=f"u{uuid.uuid4().hex[:8]}@t.local",
        password_hash="x",
        status=UserStatus.active,
    )
    db_session.add(user)
    db_session.flush()
    return user.id


def _question(db_session, org_id, *, q_type=QuestionType.single_choice) -> Question:
    q = Question(organization_id=org_id, question_type=q_type)
    db_session.add(q)
    db_session.flush()
    return q


def test_essay_is_a_question_type():
    assert QuestionType("essay") is QuestionType.essay


def test_paper_and_paper_question_roundtrip(db_session):
    org = _org_id(db_session)
    q1 = _question(db_session, org)
    q2 = _question(db_session, org)
    paper = Paper(
        organization_id=org,
        name="模拟试卷一.安全与风险管理",
        duration_minutes=180,
        total_score=173,
        question_count=2,
        dataset_slug="mockpapers",
        paper_external_id="2026082521350019232",
        domain_number=1,
    )
    paper.questions.extend([
        PaperQuestion(question_id=q1.id, position=1, score=1),
        PaperQuestion(question_id=q2.id, position=2, score=2),
    ])
    db_session.add(paper)
    db_session.flush()

    row = db_session.execute(select(Paper)).scalar_one()
    assert row.status is PaperStatus.published
    assert row.dataset_slug == "mockpapers"
    assert row.paper_external_id == "2026082521350019232"
    ordered = sorted(row.questions, key=lambda pq: pq.position)
    assert [pq.question_id for pq in ordered] == [q1.id, q2.id]
    assert [pq.score for pq in ordered] == [1, 2]
    assert row.total_score == 173


def test_paper_unique_dataset_external_id(db_session):
    org = _org_id(db_session)
    db_session.add_all([
        Paper(organization_id=org, name="a", question_count=0, total_score=0,
              dataset_slug="mockpapers", paper_external_id="dup"),
        Paper(organization_id=org, name="b", question_count=0, total_score=0,
              dataset_slug="mockpapers", paper_external_id="dup"),
    ])
    import pytest
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_translation_reference_answer_nullable(db_session):
    org = _org_id(db_session)
    q = _question(db_session, org, q_type=QuestionType.essay)
    db_session.add(QuestionTranslation(
        question_id=q.id,
        language="zh",
        stem="简述最小特权原则。",
        correct_answer_rationale="",
        options=[],
        reference_answer="只授予完成任务所必需的最小权限。",
    ))
    db_session.flush()

    row = db_session.execute(
        select(QuestionTranslation)
        .where(QuestionTranslation.question_id == q.id)
    ).scalar_one()
    assert row.reference_answer == "只授予完成任务所必需的最小权限。"


def test_user_question_state_wrong_book_columns(db_session):
    org = _org_id(db_session)
    user = _user_id(db_session)
    q = _question(db_session, org)
    state = UserQuestionState(user_id=user, question_id=q.id)
    db_session.add(state)
    db_session.flush()

    assert state.wrong_count == 0
    assert state.last_wrong_at is None

    state.wrong_count += 1
    state.last_wrong_at = datetime.now(timezone.utc)
    db_session.flush()
    refreshed = db_session.execute(
        select(UserQuestionState).where(UserQuestionState.user_id == user)
    ).scalar_one()
    assert refreshed.wrong_count == 1
    assert refreshed.last_wrong_at is not None
