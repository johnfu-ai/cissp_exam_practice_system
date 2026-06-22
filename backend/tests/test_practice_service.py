"""Service-layer tests for practice API (sub-project E)."""

from datetime import datetime, timezone

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


def test_create_session_random_pick(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    for i in range(5):
        _question(db_session, org, actor, stem=f"q{i}")
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=3),
    )
    assert s.total_questions == 3
    assert len(s.config["question_ids"]) == 3
    assert s.config["subset"] == "all"
    assert s.config["order_mode"] == "random"


def test_create_session_scope_by_domain(db_session):
    from app.models.question import QuestionMapping
    from app.models.taxonomy import ExamBlueprint, ExamDomain

    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = ExamBlueprint(version_label="v1", effective_date="2026-04-15",
                       min_items=100, max_items=150, duration_minutes=180,
                       passing_score=700, max_score=1000, is_current=False)
    db_session.add(bp)
    db_session.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=10)
    db_session.add(dom)
    db_session.flush()
    in_q = _question(db_session, org, actor, stem="in")
    _question(db_session, org, actor, stem="out")
    db_session.add(QuestionMapping(question_id=in_q.id, domain_id=dom.id))
    db_session.flush()
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=10, domain_id=dom.id),
    )
    assert s.total_questions == 1
    assert s.config["question_ids"] == [str(in_q.id)]


def test_create_session_empty_scope_rejected(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    with pytest.raises(svc.ValidationError):
        svc.create_session(
            db_session, org_id=org.id, actor_id=actor.id,
            payload=SessionCreateIn(count=10),
        )


def test_create_session_subset_unpracticed(db_session):
    from app.models.question import QuestionMapping  # noqa: F401

    org = _org(db_session)
    actor = _actor(db_session, org)
    q1 = _question(db_session, org, actor, stem="done")
    q2 = _question(db_session, org, actor, stem="new")
    other = PracticeSession(
        user_id=actor.id, organization_id=org.id,
        status=PracticeSessionStatus.completed, total_questions=1,
    )
    db_session.add(other)
    db_session.flush()
    db_session.add(PracticeAnswer(
        session_id=other.id, user_id=actor.id, question_id=q1.id,
        question_snapshot={}, options_snapshot=[], user_answer={"selected": [0]},
        is_correct=True,
    ))
    db_session.flush()
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=10, subset="unpracticed", order_mode="sequential"),
    )
    assert s.config["question_ids"] == [str(q2.id)]


def test_create_session_scope_by_chapter(db_session):
    from app.models.question import Book, Chapter, QuestionMapping

    org = _org(db_session)
    actor = _actor(db_session, org)
    book = Book(organization_id=org.id, title="B")
    db_session.add(book)
    db_session.flush()
    ch = Chapter(organization_id=org.id, book_id=book.id, order_index=0, title="C1")
    db_session.add(ch)
    db_session.flush()
    in_q = _question(db_session, org, actor, stem="in")
    _question(db_session, org, actor, stem="out")
    db_session.add(QuestionMapping(question_id=in_q.id, chapter_id=ch.id))
    db_session.flush()
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=10, chapter_ids=[ch.id], order_mode="sequential"),
    )
    assert s.config["question_ids"] == [str(in_q.id)]


def _start(db_session, org, actor, count=1):
    return svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=count, order_mode="sequential"),
    )


def test_get_question_strips_correctness(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor, stem="q1")
    s = _start(db_session, org, actor)
    out = svc.get_question_at(
        db_session, session_id=s.id, position=0, user_id=actor.id
    )
    assert out["position"] == 0
    assert out["total"] == 1
    assert out["stem"] == "q1"
    for opt in out["options"]:
        assert "is_correct" not in opt


def test_submit_answer_judges_from_snapshot(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor, stem="q1")  # option 0 correct
    s = _start(db_session, org, actor)
    started = datetime.now(timezone.utc)
    result = svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=started),
    )
    assert result.is_correct is True
    assert result.correct_indexes == [0]
    assert result.selected_indexes == [0]


def test_submit_answer_incorrect(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor, stem="q1")  # 0 correct
    s = _start(db_session, org, actor)
    result = svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[1], started_at=datetime.now(timezone.utc)),
    )
    assert result.is_correct is False
    assert s.correct_count == 0


def test_submit_answer_multiple_choice(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(
        db_session, org, actor, stem="multi", qtype=QuestionType.multiple_choice,
        options=[(0, "A", True), (1, "B", True), (2, "C", False)],
    )
    s = _start(db_session, org, actor)
    r1 = svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    assert r1.is_correct is False


def test_submit_answer_persists_snapshot(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    q = _question(db_session, org, actor, stem="q1")
    s = _start(db_session, org, actor)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    ans = db_session.query(PracticeAnswer).filter_by(session_id=s.id).one()
    assert ans.question_snapshot["question_id"] == str(q.id)
    assert ans.is_correct is True
    assert ans.user_answer == {"selected": [0]}


def test_re_answer_refused(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor)
    s = _start(db_session, org, actor)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    with pytest.raises(svc.ConflictError):
        svc.submit_answer(
            db_session, session_id=s.id, user_id=actor.id,
            payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
        )


def test_pause_resume(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor)
    s = _start(db_session, org, actor)
    svc.pause_session(db_session, session_id=s.id, user_id=actor.id)
    assert db_session.get(PracticeSession, s.id).paused_at is not None
    with pytest.raises(svc.ConflictError):
        svc.submit_answer(
            db_session, session_id=s.id, user_id=actor.id,
            payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
        )
    svc.resume_session(db_session, session_id=s.id, user_id=actor.id)
    assert db_session.get(PracticeSession, s.id).paused_at is None
    r = svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    assert r.is_correct is True


def test_finish_summary(db_session):
    from app.models.question import QuestionMapping
    from app.models.taxonomy import ExamBlueprint, ExamDomain

    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = ExamBlueprint(version_label="v1", effective_date="2026-04-15",
                       min_items=100, max_items=150, duration_minutes=180,
                       passing_score=700, max_score=1000, is_current=False)
    db_session.add(bp)
    db_session.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=10)
    db_session.add(dom)
    db_session.flush()
    q1 = _question(db_session, org, actor, stem="right")  # 0 correct
    q2 = _question(db_session, org, actor, stem="wrong")  # 0 correct
    db_session.add(QuestionMapping(question_id=q1.id, domain_id=dom.id))
    db_session.add(QuestionMapping(question_id=q2.id, domain_id=dom.id))
    db_session.flush()
    s = _start(db_session, org, actor, count=2)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=1, selected=[1], started_at=datetime.now(timezone.utc)),
    )
    summary = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert summary.total_questions == 2
    assert summary.answered_count == 2
    assert summary.correct_count == 1
    assert summary.accuracy == 0.5
    assert len(summary.domains) == 1
    assert summary.domains[0].answered == 2
    assert summary.domains[0].correct == 1
    assert len(summary.wrong_questions) == 1
    assert summary.wrong_questions[0].question_id == q2.id
    assert db_session.get(PracticeSession, s.id).status == PracticeSessionStatus.completed


def test_finish_idempotent(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor)
    s = _start(db_session, org, actor)
    a = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    b = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert a.correct_count == b.correct_count


def test_other_user_session_not_found(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    intruder = _actor(db_session, org, email="other@example.com")
    _question(db_session, org, actor)
    s = _start(db_session, org, actor)
    with pytest.raises(svc.NotFound):
        svc.finish_session(db_session, session_id=s.id, user_id=intruder.id)
