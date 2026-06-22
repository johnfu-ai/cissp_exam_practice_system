"""Service-layer tests for analytics (sub-project H1, Task 4).

Covers dashboard, domain_mastery, trend and the internal helpers.
Seeds users/orgs/blueprints/domains/questions/answers directly on the
real ``cissp_test`` DB using the same module-level helper style as
``test_exam_service.py`` and ``test_practice_service.py``.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.auth import Organization, User
from app.models.enums import (
    ExamSessionKind,
    ExamSessionStatus,
    OrgKind,
    PracticeSessionStatus,
    QuestionStatus,
    QuestionType,
    TextFormat,
)
from app.models.exam import ExamAnswer, ExamSession
from app.models.practice import PracticeAnswer, PracticeSession
from app.models.question import Question, QuestionMapping, QuestionOption
from app.models.taxonomy import ExamBlueprint, ExamDomain
from app.services import analytics


# --------------------------------------------------------------------------- #
# Module-level seed helpers (match the conventions in test_exam_service.py)
# --------------------------------------------------------------------------- #

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


def _question(db_session, org, actor, *, stem="q"):
    """Single-choice question with option 0 correct, option 1 wrong."""
    q = Question(
        organization_id=org.id,
        question_type=QuestionType.single_choice,
        stem=stem,
        stem_format=TextFormat.markdown,
        status=QuestionStatus.published,
        created_by_id=actor.id,
    )
    db_session.add(q)
    db_session.flush()
    db_session.add(QuestionOption(
        question_id=q.id, order_index=0, content="A",
        content_format=TextFormat.markdown, is_correct=True,
    ))
    db_session.add(QuestionOption(
        question_id=q.id, order_index=1, content="B",
        content_format=TextFormat.markdown, is_correct=False,
    ))
    db_session.flush()
    return q


def _blueprint(db_session, *, current=True, version="v1"):
    bp = ExamBlueprint(
        version_label=version,
        effective_date="2026-04-15",
        min_items=1,
        max_items=10,
        duration_minutes=30,
        passing_score=700,
        max_score=1000,
        is_current=current,
    )
    db_session.add(bp)
    db_session.flush()
    return bp


def _domain(db_session, bp, *, number, name, weight_pct):
    d = ExamDomain(
        blueprint_id=bp.id, number=number, name=name, weight_pct=weight_pct,
    )
    db_session.add(d)
    db_session.flush()
    return d


def _map(db_session, question, domain):
    m = QuestionMapping(question_id=question.id, domain_id=domain.id)
    db_session.add(m)
    db_session.flush()
    return m


def _practice_session(db_session, org, actor):
    s = PracticeSession(
        user_id=actor.id,
        organization_id=org.id,
        status=PracticeSessionStatus.completed,
        total_questions=1,
    )
    db_session.add(s)
    db_session.flush()
    return s


def _exam_session(db_session, org, actor, bp):
    s = ExamSession(
        user_id=actor.id,
        organization_id=org.id,
        blueprint_id=bp.id,
        session_kind=ExamSessionKind.fixed,
        status=ExamSessionStatus.completed,
        total_questions=1,
    )
    db_session.add(s)
    db_session.flush()
    return s


def _practice_answer(db_session, *, session, actor, question, is_correct,
                     time_spent_ms=1000, answered_at=None):
    ans = PracticeAnswer(
        session_id=session.id,
        user_id=actor.id,
        question_id=question.id,
        question_snapshot={},
        options_snapshot=[],
        user_answer={"selected": [0]},
        is_correct=is_correct,
        time_spent_ms=time_spent_ms,
        answered_at=answered_at or datetime.now(timezone.utc),
    )
    db_session.add(ans)
    db_session.flush()
    return ans


def _exam_answer(db_session, *, session, actor, question, is_correct,
                 time_spent_ms=2000, answered_at=None):
    ans = ExamAnswer(
        session_id=session.id,
        user_id=actor.id,
        question_id=question.id,
        question_snapshot={},
        options_snapshot=[],
        user_answer={"selected": [0]},
        is_correct=is_correct,
        time_spent_ms=time_spent_ms,
        answered_at=answered_at or datetime.now(timezone.utc),
    )
    db_session.add(ans)
    db_session.flush()
    return ans


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def learner(db_session):
    """A user + personal org (no answers, no blueprint)."""
    org = _org(db_session)
    return _actor(db_session, org)


@pytest.fixture
def seeded_answers(db_session, learner):
    """4 practice answers (3 correct) + 1 exam answer (correct), all today.

    Distinct questions so ``practiced_questions`` == 5 and
    ``study_time_ms`` == 1000+1500+2000+2500+3000 == 10000.
    """
    org = db_session.get(Organization, learner.default_organization_id)
    ps = _practice_session(db_session, org, learner)
    es_bp = _blueprint(db_session, version="exam-v1")
    es = _exam_session(db_session, org, learner, es_bp)
    qs = [_question(db_session, org, learner, stem=f"q{i}") for i in range(5)]
    _practice_answer(db_session, session=ps, actor=learner, question=qs[0],
                     is_correct=True, time_spent_ms=1000)
    _practice_answer(db_session, session=ps, actor=learner, question=qs[1],
                     is_correct=True, time_spent_ms=1500)
    _practice_answer(db_session, session=ps, actor=learner, question=qs[2],
                     is_correct=True, time_spent_ms=2000)
    _practice_answer(db_session, session=ps, actor=learner, question=qs[3],
                     is_correct=False, time_spent_ms=2500)
    _exam_answer(db_session, session=es, actor=learner, question=qs[4],
                 is_correct=True, time_spent_ms=3000)


@pytest.fixture
def seeded_answers_gap(db_session, learner):
    """A single answer 3 days ago -> streak 0 (today not in dates set)."""
    org = db_session.get(Organization, learner.default_organization_id)
    ps = _practice_session(db_session, org, learner)
    q = _question(db_session, org, learner, stem="gap-q")
    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
    _practice_answer(db_session, session=ps, actor=learner, question=q,
                     is_correct=True, time_spent_ms=1000,
                     answered_at=three_days_ago)


@pytest.fixture
def current_bp(db_session):
    """A current blueprint with 8 ExamDomain rows (only domain 1 gets answers)."""
    bp = _blueprint(db_session, current=True, version="dm-v1")
    for n in range(1, 9):
        _domain(db_session, bp, number=n, name=f"D{n}", weight_pct=12)
    return bp


@pytest.fixture
def domain_answers(db_session, learner, current_bp):
    """2 practice + 1 exam answers in domain 1 (2 correct of 3).

    Times 2000 + 3000 + 4000 -> avg_time_ms == 3000.
    Accuracy 2/3 == 0.6667 -> mastery_level ``reviewing`` (>= 0.6).
    """
    org = db_session.get(Organization, learner.default_organization_id)
    d1 = db_session.query(ExamDomain).filter_by(
        blueprint_id=current_bp.id, number=1
    ).one()
    ps = _practice_session(db_session, org, learner)
    es = _exam_session(db_session, org, learner, current_bp)
    q1 = _question(db_session, org, learner, stem="d1-q1")
    q2 = _question(db_session, org, learner, stem="d1-q2")
    q3 = _question(db_session, org, learner, stem="d1-q3")
    _map(db_session, q1, d1)
    _map(db_session, q2, d1)
    _map(db_session, q3, d1)
    _practice_answer(db_session, session=ps, actor=learner, question=q1,
                     is_correct=True, time_spent_ms=2000)
    _practice_answer(db_session, session=ps, actor=learner, question=q2,
                     is_correct=False, time_spent_ms=3000)
    _exam_answer(db_session, session=es, actor=learner, question=q3,
                 is_correct=True, time_spent_ms=4000)


@pytest.fixture
def trend_answers(db_session, learner):
    """2 distinct active UTC days within the 30-day window (today + yesterday).

    Today: 1 correct. Yesterday: 1 wrong. -> 2 points.
    """
    org = db_session.get(Organization, learner.default_organization_id)
    ps = _practice_session(db_session, org, learner)
    q1 = _question(db_session, org, learner, stem="t1")
    q2 = _question(db_session, org, learner, stem="t2")
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    _practice_answer(db_session, session=ps, actor=learner, question=q1,
                     is_correct=True, time_spent_ms=1000, answered_at=now)
    _practice_answer(db_session, session=ps, actor=learner, question=q2,
                     is_correct=False, time_spent_ms=2000, answered_at=yesterday)


# --------------------------------------------------------------------------- #
# Tests — dashboard
# --------------------------------------------------------------------------- #

def test_dashboard_empty_user(db_session, learner):
    out = analytics.dashboard(db_session, user_id=learner.id)
    assert out.total_answered == 0
    assert out.correct_count == 0
    assert out.accuracy == 0.0
    assert out.streak_days == 0
    assert out.study_time_ms == 0
    assert out.last_active_at is None
    assert out.practiced_questions == 0


def test_dashboard_counts_and_streak(db_session, learner, seeded_answers):
    out = analytics.dashboard(db_session, user_id=learner.id)
    assert out.total_answered == 5
    assert out.correct_count == 4
    assert out.accuracy == round(4 / 5, 4)
    assert out.streak_days >= 1  # answered today
    # Real computed values (not mocks):
    assert out.practiced_questions == 5  # 5 distinct questions
    assert out.study_time_ms == 10000  # 1000+1500+2000+2500+3000
    assert out.last_active_at is not None


def test_dashboard_streak_breaks_on_gap(db_session, learner, seeded_answers_gap):
    # answers only on a day 3 days ago -> streak 0
    out = analytics.dashboard(db_session, user_id=learner.id)
    assert out.streak_days == 0
    assert out.total_answered == 1
    assert out.last_active_at is not None


# --------------------------------------------------------------------------- #
# Tests — domain_mastery
# --------------------------------------------------------------------------- #

def test_domain_mastery_merges_practice_and_exam(
    db_session, learner, current_bp, domain_answers
):
    out = analytics.domain_mastery(
        db_session, user_id=learner.id, blueprint=current_bp
    )
    assert len(out) == 8
    dom1 = next(d for d in out if d.number == 1)
    # 2 practice + 1 exam answers in domain 1, 2 correct
    assert dom1.answered == 3
    assert dom1.correct == 2
    assert dom1.avg_time_ms > 0
    # Real computed values:
    assert dom1.avg_time_ms == 3000  # (2000 + 3000 + 4000) / 3
    assert dom1.accuracy == round(2 / 3, 4)  # 0.6667
    assert dom1.mastery_level == "reviewing"  # 0.6667 >= 0.6
    assert dom1.name == "D1"
    assert dom1.weight_pct == 12
    # Ordering by domain number ascending
    assert [d.number for d in out] == list(range(1, 9))


def test_domain_mastery_empty_domain_is_not_started(
    db_session, learner, current_bp, domain_answers
):
    out = analytics.domain_mastery(
        db_session, user_id=learner.id, blueprint=current_bp
    )
    dom2 = next(d for d in out if d.number == 2)
    assert dom2.answered == 0
    assert dom2.correct == 0
    assert dom2.accuracy == 0.0
    assert dom2.avg_time_ms == 0
    assert dom2.mastery_level == "not_started"  # 0.0 < 0.4


def test_domain_mastery_no_blueprint(db_session, learner):
    out = analytics.domain_mastery(
        db_session, user_id=learner.id, blueprint=None
    )
    assert out == []


def test_domain_mastery_empty_user(db_session, learner, current_bp):
    out = analytics.domain_mastery(
        db_session, user_id=learner.id, blueprint=current_bp
    )
    assert len(out) == 8
    assert all(d.answered == 0 for d in out)
    assert all(d.mastery_level == "not_started" for d in out)


# --------------------------------------------------------------------------- #
# Tests — trend
# --------------------------------------------------------------------------- #

def test_trend_30d_buckets_by_day(db_session, learner, trend_answers):
    out = analytics.trend(db_session, user_id=learner.id, window_days=30)
    assert out.window_days == 30
    assert len(out.points) == 2  # two distinct active days
    # Points sorted ascending by date; each accuracy == correct/answered.
    assert all(
        p.accuracy == round(p.correct / p.answered, 4) for p in out.points
    )
    # Real computed values: yesterday (1 wrong), today (1 correct).
    assert out.points[0].answered == 1
    assert out.points[0].correct == 0
    assert out.points[0].accuracy == 0.0
    assert out.points[1].answered == 1
    assert out.points[1].correct == 1
    assert out.points[1].accuracy == 1.0


def test_trend_empty_user(db_session, learner):
    out = analytics.trend(db_session, user_id=learner.id, window_days=30)
    assert out.window_days == 30
    assert out.points == []


def test_trend_invalid_window_raises(db_session, learner):
    with pytest.raises(ValueError):
        analytics.trend(db_session, user_id=learner.id, window_days=7)


def test_trend_90d_accepted(db_session, learner, trend_answers):
    out = analytics.trend(db_session, user_id=learner.id, window_days=90)
    assert out.window_days == 90
    assert len(out.points) == 2  # both days within 90d window
