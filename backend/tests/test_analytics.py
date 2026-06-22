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
    ErrorType,
    ExamSessionKind,
    ExamSessionStatus,
    MasteryLevel,
    OrgKind,
    PracticeSessionStatus,
    QuestionStatus,
    QuestionType,
    TextFormat,
)
from app.models.exam import ExamAnswer, ExamSession
from app.models.practice import PracticeAnswer, PracticeSession, UserQuestionState
from app.models.question import Question, QuestionMapping, QuestionOption
from app.models.taxonomy import ExamBlueprint, ExamDomain, KnowledgePoint
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


def _map(db_session, question, domain, knowledge_point=None):
    m = QuestionMapping(
        question_id=question.id,
        domain_id=domain.id,
        knowledge_point_id=knowledge_point.id if knowledge_point else None,
    )
    db_session.add(m)
    db_session.flush()
    return m


def _kp(db_session, name):
    """Global KnowledgePoint row."""
    kp = KnowledgePoint(name=name)
    db_session.add(kp)
    db_session.flush()
    return kp


def _state(db_session, *, user, question, mastery_level=None, error_type=None):
    """UserQuestionState for user+question (mastery_level / error_type optional)."""
    st = UserQuestionState(
        user_id=user.id,
        question_id=question.id,
        mastery_level=mastery_level or MasteryLevel.not_started,
        error_type=error_type,
    )
    db_session.add(st)
    db_session.flush()
    return st


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


# --------------------------------------------------------------------------- #
# Tests — weak_areas, error_type_breakdown, recommendation, personal_report
# (Task 5)
# --------------------------------------------------------------------------- #

@pytest.fixture
def weak_area_setup(db_session, learner):
    """Three domains + one knowledge point:

    - Domain 1: 3 answers (1 correct, 2 wrong) -> accuracy 0.3333, weak
    - Domain 2: 2 answers (1 correct, 1 wrong) -> accuracy 0.5, NOT weak
      (only 2 answered, below the >=3 threshold)
    - Domain 3: 3 answers (0 correct, 3 wrong) -> accuracy 0.0, weak (weakest)
    - KP1 (mapped to Domain 1 questions): 3 answers (1 correct, 2 wrong) -> weak
    """
    org = db_session.get(Organization, learner.default_organization_id)
    bp = _blueprint(db_session, current=False, version="weak-v1")
    d1 = _domain(db_session, bp, number=1, name="Domain 1", weight_pct=34)
    d2 = _domain(db_session, bp, number=2, name="Domain 2", weight_pct=33)
    d3 = _domain(db_session, bp, number=3, name="Domain 3", weight_pct=33)
    kp1 = _kp(db_session, "KP1")
    ps = _practice_session(db_session, org, learner)
    # Domain 1: 3 answers, 1 correct (accuracy 0.3333) — mapped to KP1
    q1 = _question(db_session, org, learner, stem="d1-q1")
    q2 = _question(db_session, org, learner, stem="d1-q2")
    q3 = _question(db_session, org, learner, stem="d1-q3")
    _map(db_session, q1, d1, knowledge_point=kp1)
    _map(db_session, q2, d1, knowledge_point=kp1)
    _map(db_session, q3, d1, knowledge_point=kp1)
    _practice_answer(db_session, session=ps, actor=learner, question=q1,
                     is_correct=True)
    _practice_answer(db_session, session=ps, actor=learner, question=q2,
                     is_correct=False)
    _practice_answer(db_session, session=ps, actor=learner, question=q3,
                     is_correct=False)
    # Domain 2: 2 answers, 1 correct (accuracy 0.5) — NOT weak (<3 answered)
    q4 = _question(db_session, org, learner, stem="d2-q4")
    q5 = _question(db_session, org, learner, stem="d2-q5")
    _map(db_session, q4, d2)
    _map(db_session, q5, d2)
    _practice_answer(db_session, session=ps, actor=learner, question=q4,
                     is_correct=True)
    _practice_answer(db_session, session=ps, actor=learner, question=q5,
                     is_correct=False)
    # Domain 3: 3 answers, 0 correct (accuracy 0.0) — weakest
    q6 = _question(db_session, org, learner, stem="d3-q6")
    q7 = _question(db_session, org, learner, stem="d3-q7")
    q8 = _question(db_session, org, learner, stem="d3-q8")
    _map(db_session, q6, d3)
    _map(db_session, q7, d3)
    _map(db_session, q8, d3)
    _practice_answer(db_session, session=ps, actor=learner, question=q6,
                     is_correct=False)
    _practice_answer(db_session, session=ps, actor=learner, question=q7,
                     is_correct=False)
    _practice_answer(db_session, session=ps, actor=learner, question=q8,
                     is_correct=False)


@pytest.fixture
def error_type_setup(db_session, learner):
    """4 wrong answers across 4 distinct questions + 1 correct answer:

    - q1, q2: error_type=concept_unclear (2 wrong, classified)
    - q3:     error_type=misread_stem     (1 wrong, classified)
    - q4:     no UserQuestionState         (1 wrong, unclassified -> None bucket)
    - q5:     correct                      (not counted as wrong)
    """
    org = db_session.get(Organization, learner.default_organization_id)
    ps = _practice_session(db_session, org, learner)
    q1 = _question(db_session, org, learner, stem="et-q1")
    q2 = _question(db_session, org, learner, stem="et-q2")
    q3 = _question(db_session, org, learner, stem="et-q3")
    q4 = _question(db_session, org, learner, stem="et-q4")
    q5 = _question(db_session, org, learner, stem="et-q5")
    _practice_answer(db_session, session=ps, actor=learner, question=q1,
                     is_correct=False)
    _practice_answer(db_session, session=ps, actor=learner, question=q2,
                     is_correct=False)
    _practice_answer(db_session, session=ps, actor=learner, question=q3,
                     is_correct=False)
    _practice_answer(db_session, session=ps, actor=learner, question=q4,
                     is_correct=False)
    _practice_answer(db_session, session=ps, actor=learner, question=q5,
                     is_correct=True)
    _state(db_session, user=learner, question=q1,
           error_type=ErrorType.concept_unclear)
    _state(db_session, user=learner, question=q2,
           error_type=ErrorType.concept_unclear)
    _state(db_session, user=learner, question=q3,
           error_type=ErrorType.misread_stem)
    # q4 intentionally has NO UserQuestionState -> falls into the None bucket.


@pytest.fixture
def recommendation_setup(db_session, learner, current_bp):
    """Weak domain 1 (in current_bp) with 3 wrong answers; q1 is mastered.

    Returns the mastered question id — it MUST be excluded from
    next_practice_question_ids (mastered questions are not candidates).
    """
    org = db_session.get(Organization, learner.default_organization_id)
    d1 = db_session.query(ExamDomain).filter_by(
        blueprint_id=current_bp.id, number=1
    ).one()
    ps = _practice_session(db_session, org, learner)
    q1 = _question(db_session, org, learner, stem="rec-q1")  # will be mastered
    q2 = _question(db_session, org, learner, stem="rec-q2")
    q3 = _question(db_session, org, learner, stem="rec-q3")
    _map(db_session, q1, d1)
    _map(db_session, q2, d1)
    _map(db_session, q3, d1)
    now = datetime.now(timezone.utc)
    # Distinct answered_at so least-recently-practiced ordering is deterministic.
    _practice_answer(db_session, session=ps, actor=learner, question=q1,
                     is_correct=False, answered_at=now - timedelta(minutes=30))
    _practice_answer(db_session, session=ps, actor=learner, question=q2,
                     is_correct=False, answered_at=now - timedelta(minutes=20))
    _practice_answer(db_session, session=ps, actor=learner, question=q3,
                     is_correct=False, answered_at=now - timedelta(minutes=10))
    _state(db_session, user=learner, question=q1,
           mastery_level=MasteryLevel.mastered)
    return q1.id


@pytest.fixture
def recommendation_mastered_correct_setup(db_session, learner, current_bp):
    """Weak domain 1 (in current_bp) with a mastered-but-CORRECT question.

    - q1: answered CORRECTLY, mastery_level=mastered (the leak candidate).
      q1 is NOT in wrong_qids, so the old mastered_qids (built from wrong-only
      states) missed it — it leaked into next_practice_question_ids.
    - q2, q3, q4: answered wrong -> domain accuracy 1/4 = 0.25, weak.

    Returns the mastered-correct question id — it MUST be excluded from
    next_practice_question_ids even though it is correct (not wrong).
    """
    org = db_session.get(Organization, learner.default_organization_id)
    d1 = db_session.query(ExamDomain).filter_by(
        blueprint_id=current_bp.id, number=1
    ).one()
    ps = _practice_session(db_session, org, learner)
    q1 = _question(db_session, org, learner, stem="rec-correct-q1")
    q2 = _question(db_session, org, learner, stem="rec-correct-q2")
    q3 = _question(db_session, org, learner, stem="rec-correct-q3")
    q4 = _question(db_session, org, learner, stem="rec-correct-q4")
    _map(db_session, q1, d1)
    _map(db_session, q2, d1)
    _map(db_session, q3, d1)
    _map(db_session, q4, d1)
    now = datetime.now(timezone.utc)
    _practice_answer(db_session, session=ps, actor=learner, question=q1,
                     is_correct=True, answered_at=now - timedelta(minutes=40))
    _practice_answer(db_session, session=ps, actor=learner, question=q2,
                     is_correct=False, answered_at=now - timedelta(minutes=30))
    _practice_answer(db_session, session=ps, actor=learner, question=q3,
                     is_correct=False, answered_at=now - timedelta(minutes=20))
    _practice_answer(db_session, session=ps, actor=learner, question=q4,
                     is_correct=False, answered_at=now - timedelta(minutes=10))
    _state(db_session, user=learner, question=q1,
           mastery_level=MasteryLevel.mastered)
    return q1.id


@pytest.fixture
def recommendation_duplicate_wrong_setup(db_session, learner, current_bp):
    """Weak domain 1 where q1 is answered wrong TWICE (plus q2, q3 wrong once).

    Used to assert wrong_to_review has no duplicate question ids.
    """
    org = db_session.get(Organization, learner.default_organization_id)
    d1 = db_session.query(ExamDomain).filter_by(
        blueprint_id=current_bp.id, number=1
    ).one()
    ps = _practice_session(db_session, org, learner)
    q1 = _question(db_session, org, learner, stem="dedup-q1")
    q2 = _question(db_session, org, learner, stem="dedup-q2")
    q3 = _question(db_session, org, learner, stem="dedup-q3")
    _map(db_session, q1, d1)
    _map(db_session, q2, d1)
    _map(db_session, q3, d1)
    now = datetime.now(timezone.utc)
    _practice_answer(db_session, session=ps, actor=learner, question=q1,
                     is_correct=False, answered_at=now - timedelta(minutes=30))
    _practice_answer(db_session, session=ps, actor=learner, question=q1,
                     is_correct=False, answered_at=now - timedelta(minutes=20))
    _practice_answer(db_session, session=ps, actor=learner, question=q2,
                     is_correct=False, answered_at=now - timedelta(minutes=10))
    _practice_answer(db_session, session=ps, actor=learner, question=q3,
                     is_correct=False, answered_at=now)
    return q1.id


# --------------------------------------------------------------------------- #
# weak_areas
# --------------------------------------------------------------------------- #

def test_weak_areas_threshold_and_order(db_session, learner, weak_area_setup):
    out = analytics.weak_areas(db_session, user_id=learner.id)
    # A domain with accuracy 0.33 over 3 answers is weak; a domain with
    # accuracy 0.5 over 2 is NOT (<3 answered).
    assert any(w.label.startswith("Domain") and w.accuracy < 0.6
               for w in out.weak_domains)
    assert all(w.answered >= 3 for w in out.weak_domains)
    assert all(w.accuracy < 0.6 for w in out.weak_domains)
    # Domain 2 (2 answered) must NOT appear; Domain 1 and Domain 3 must.
    labels = {w.label for w in out.weak_domains}
    assert "Domain 1" in labels
    assert "Domain 3" in labels
    assert "Domain 2" not in labels
    # Sorted accuracy ascending: Domain 3 (0.0) before Domain 1 (0.3333).
    assert len(out.weak_domains) == 2
    assert out.weak_domains[0].accuracy <= out.weak_domains[1].accuracy
    assert out.weak_domains[0].accuracy == 0.0
    assert out.weak_domains[1].accuracy == round(1 / 3, 4)


def test_weak_areas_knowledge_points(db_session, learner, weak_area_setup):
    out = analytics.weak_areas(db_session, user_id=learner.id)
    # KP1 has 3 answers (1 correct, 2 wrong) -> accuracy 0.3333, weak.
    assert len(out.weak_knowledge_points) == 1
    w = out.weak_knowledge_points[0]
    assert w.knowledge_point_id is not None
    assert w.domain_id is None
    assert w.label == "KP1"
    assert w.answered == 3
    assert w.correct == 1
    assert w.accuracy == round(1 / 3, 4)


def test_weak_areas_empty_user(db_session, learner):
    out = analytics.weak_areas(db_session, user_id=learner.id)
    assert out.weak_domains == []
    assert out.weak_knowledge_points == []


# --------------------------------------------------------------------------- #
# error_type_breakdown
# --------------------------------------------------------------------------- #

def test_error_type_breakdown(db_session, learner, error_type_setup):
    out = analytics.error_type_breakdown(db_session, user_id=learner.id)
    types = {b.error_type: b.count for b in out.distribution}
    assert types.get("concept_unclear") == 2
    assert types.get("misread_stem") == 1
    assert types.get(None) >= 1  # unclassified bucket present
    # 4 wrong questions total; 3 classified (q1, q2, q3) + 1 unclassified (q4).
    assert out.total_wrong_classified == 3


def test_error_type_breakdown_empty_user(db_session, learner):
    out = analytics.error_type_breakdown(db_session, user_id=learner.id)
    assert out.total_wrong_classified == 0
    # None bucket is always present (even when empty).
    assert {b.error_type for b in out.distribution} == {None}
    assert out.distribution[0].count == 0


# --------------------------------------------------------------------------- #
# recommendation
# --------------------------------------------------------------------------- #

def test_recommendation_focus_weakest(
    db_session, learner, current_bp, recommendation_setup
):
    mastered_qid = recommendation_setup
    out = analytics.recommendation(
        db_session, user_id=learner.id, blueprint=current_bp
    )
    assert out.focus_domain is not None
    assert out.focus_domain.label == "D1"  # weakest domain in current_bp
    assert len(out.next_practice_question_ids) <= 10
    # Mastered questions excluded from next_practice.
    assert mastered_qid not in out.next_practice_question_ids
    # The two non-mastered wrong questions in D1 are the candidates,
    # ordered least-recently-practiced first (q2 answered before q3).
    assert len(out.next_practice_question_ids) == 2
    # Mastered question excluded from wrong_to_review as well.
    assert mastered_qid not in out.wrong_to_review
    assert len(out.wrong_to_review) == 2
    assert out.rationale.startswith("Focus on your weakest domain")


def test_recommendation_no_blueprint(db_session, learner):
    out = analytics.recommendation(
        db_session, user_id=learner.id, blueprint=None
    )
    assert out.focus_domain is None
    assert out.next_practice_question_ids == []
    assert out.wrong_to_review == []
    assert "blueprint" in out.rationale.lower()


def test_recommendation_no_weak_areas(db_session, learner, current_bp):
    # No answers -> no weak areas -> focus_domain None, empty lists.
    out = analytics.recommendation(
        db_session, user_id=learner.id, blueprint=current_bp
    )
    assert out.focus_domain is None
    assert out.next_practice_question_ids == []
    assert out.wrong_to_review == []
    assert "no weak areas" in out.rationale.lower()


def test_recommendation_excludes_mastered_correct_in_weak_domain(
    db_session, learner, current_bp, recommendation_mastered_correct_setup
):
    """A mastered-but-CORRECT question in a weak domain must NOT leak into
    next_practice_question_ids.

    Regression for Finding 1: mastered_qids used to be built only from
    wrong-question states, so a mastered correct question in a weak domain
    escaped exclusion. The fix queries UserQuestionState across ALL weak_qids.
    """
    mastered_correct_qid = recommendation_mastered_correct_setup
    out = analytics.recommendation(
        db_session, user_id=learner.id, blueprint=current_bp
    )
    assert out.focus_domain is not None
    assert out.focus_domain.label == "D1"  # 1/4 = 0.25 -> weak
    # The mastered-correct question must be excluded from next_practice.
    assert mastered_correct_qid not in out.next_practice_question_ids
    # The three non-mastered wrong questions (q2, q3, q4) are the candidates.
    assert len(out.next_practice_question_ids) == 3
    # It is correct, so it never enters wrong_to_review regardless.
    assert mastered_correct_qid not in out.wrong_to_review


def test_recommendation_wrong_to_review_dedup(
    db_session, learner, current_bp, recommendation_duplicate_wrong_setup
):
    """A question answered wrong twice appears only once in wrong_to_review.

    Regression for Finding 2: wrong_qids is a list comprehension, so duplicate
    wrong answers duplicated qids in wrong_to_review until sorted(set(...)).
    """
    dup_qid = recommendation_duplicate_wrong_setup
    out = analytics.recommendation(
        db_session, user_id=learner.id, blueprint=current_bp
    )
    # 3 distinct wrong questions (q1, q2, q3) — q1 not duplicated.
    assert len(out.wrong_to_review) == 3
    assert out.wrong_to_review.count(dup_qid) == 1
    # next_practice also dedups (earliest answered_at wins per distinct qid).
    assert dup_qid in out.next_practice_question_ids
    assert out.next_practice_question_ids.count(dup_qid) == 1


# --------------------------------------------------------------------------- #
# personal_report
# --------------------------------------------------------------------------- #

def test_personal_report_composes(
    db_session, learner, current_bp, recommendation_setup
):
    out = analytics.personal_report(
        db_session, user_id=learner.id, blueprint=current_bp
    )
    assert out.dashboard is not None
    assert out.dashboard.total_answered == 3  # 3 wrong answers seeded
    assert out.trend_30d.window_days == 30
    assert isinstance(out.domains, list)
    assert len(out.domains) == 8  # current_bp has 8 domains
    assert out.error_types is not None
    assert out.recommendation is not None
    assert out.recommendation.focus_domain is not None
    assert out.weak_areas.weak_domains  # domain 1 is weak
    assert out.generated_at is not None


def test_personal_report_no_blueprint(db_session, learner):
    out = analytics.personal_report(
        db_session, user_id=learner.id, blueprint=None
    )
    assert out.dashboard is not None
    assert out.trend_30d.window_days == 30
    assert out.domains == []  # no blueprint -> empty domain mastery
    assert out.recommendation.focus_domain is None
    assert out.generated_at is not None
