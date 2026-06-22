"""Analytics service — personal learning analytics (sub-project H1).

Read-only service: all queries are scoped to a single ``user_id`` and never
commit (the router layer commits / doesn't-commit as appropriate for GETs).
Empty users degrade gracefully to 200 zero/empty responses.

Covers: dashboard, domain mastery, trend (Task 4), and weak areas,
error-type breakdown, recommendation, personal report (Task 5).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ErrorType, MasteryLevel
from app.models.exam import ExamAnswer
from app.models.practice import PracticeAnswer, UserQuestionState
from app.models.question import Question, QuestionMapping
from app.models.taxonomy import ExamBlueprint, ExamDomain, KnowledgePoint
from app.schemas.analytics import (
    DashboardOut,
    DomainMasteryOut,
    ErrorTypeBreakdown,
    ErrorTypeOut,
    PersonalReportOut,
    ReviewRecommendationOut,
    TrendOut,
    TrendPoint,
    WeakAreaOut,
    WeakAreasOut,
)
from app.db.queries import not_deleted

# Allowed trend windows (PRD spec — anything else is a programmer error).
_TREND_WINDOWS = (30, 90)

# Weak-area thresholds / caps (spec — exact).
_WEAK_ACC = 0.6
_WEAK_MIN_ANSWERED = 3
_MAX_WEAK_DOMAINS = 8
_MAX_WEAK_KPS = 10
_MAX_NEXT_PRACTICE = 10


def _current_blueprint_or_none(session: Session) -> ExamBlueprint | None:
    """Return the single current ExamBlueprint, or None if none is marked current."""
    return session.execute(
        select(ExamBlueprint).where(ExamBlueprint.is_current.is_(True))
    ).scalars().first()


def _mastery_from_accuracy(acc: float) -> MasteryLevel:
    """Map an accuracy ratio in [0.0, 1.0] to a MasteryLevel.

    Thresholds (exact, per spec):
        >= 0.8 -> mastered
        >= 0.6 -> reviewing
        >= 0.4 -> learning
        else   -> not_started
    """
    if acc >= 0.8:
        return MasteryLevel.mastered
    if acc >= 0.6:
        return MasteryLevel.reviewing
    if acc >= 0.4:
        return MasteryLevel.learning
    return MasteryLevel.not_started


def _streak(days: set[date]) -> int:
    """Count consecutive days ending today (UTC) present in ``days``.

    If today is not in ``days`` the streak is 0 (a gap breaks the chain).
    """
    if not days:
        return 0
    today = datetime.now(timezone.utc).date()
    streak = 0
    day = today
    while day in days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def _answer_rows(session: Session, user_id, since=None):
    """Yield (question_id, is_correct, time_spent_ms, answered_at) tuples
    merged across practice + exam answers for ``user_id``.

    If ``since`` is given, only rows with ``answered_at >= since`` are returned.
    """
    pa = select(
        PracticeAnswer.question_id,
        PracticeAnswer.is_correct,
        PracticeAnswer.time_spent_ms,
        PracticeAnswer.answered_at,
    ).where(PracticeAnswer.user_id == user_id)
    ea = select(
        ExamAnswer.question_id,
        ExamAnswer.is_correct,
        ExamAnswer.time_spent_ms,
        ExamAnswer.answered_at,
    ).where(ExamAnswer.user_id == user_id)
    if since is not None:
        pa = pa.where(PracticeAnswer.answered_at >= since)
        ea = ea.where(ExamAnswer.answered_at >= since)
    rows = []
    rows.extend(session.execute(pa).all())
    rows.extend(session.execute(ea).all())
    return rows


def _answer_buckets(session: Session, user_id, since=None):
    """Return ``dict[domain_id] -> {answered, correct, time_ms}`` merged across
    practice + exam answers.

    Answers whose question has no QuestionMapping (no domain) are skipped.
    """
    rows = _answer_rows(session, user_id, since=since)
    qids = {r[0] for r in rows}
    if not qids:
        return {}
    dom_map = dict(
        session.execute(
            select(QuestionMapping.question_id, QuestionMapping.domain_id).where(
                QuestionMapping.question_id.in_(qids)
            )
        ).all()
    )
    buckets: dict = defaultdict(lambda: {"answered": 0, "correct": 0, "time_ms": 0})
    for qid, is_correct, tms, _answered_at in rows:
        dom = dom_map.get(qid)
        if dom is None:
            continue
        b = buckets[dom]
        b["answered"] += 1
        if is_correct:
            b["correct"] += 1
        b["time_ms"] += tms or 0
    return buckets


def dashboard(session: Session, *, user_id) -> DashboardOut:
    """Aggregate personal stats for ``user_id`` across practice + exam answers.

    Empty user -> all-zero / None response (never raises).
    """
    rows = _answer_rows(session, user_id)
    total = len(rows)
    correct = sum(1 for r in rows if r[1])
    study = sum((r[2] or 0) for r in rows)
    last = max((r[3] for r in rows), default=None)
    days = {r[3].astimezone(timezone.utc).date() for r in rows}
    return DashboardOut(
        practiced_questions=len({r[0] for r in rows}),
        total_answered=total,
        correct_count=correct,
        accuracy=round(correct / total, 4) if total else 0.0,
        study_time_ms=study,
        streak_days=_streak(days),
        last_active_at=last,
    )


def domain_mastery(
    session: Session, *, user_id, blueprint
) -> list[DomainMasteryOut]:
    """Per-domain mastery breakdown for ``user_id`` within ``blueprint``'s domains.

    ``blueprint=None`` -> ``[]`` (graceful degradation when no current blueprint).
    Returns one DomainMasteryOut per ExamDomain ordered by ``number`` ascending;
    domains with no answers report zero counts and ``not_started`` mastery.
    """
    if blueprint is None:
        return []
    domains = (
        session.execute(
            select(ExamDomain)
            .where(ExamDomain.blueprint_id == blueprint.id)
            .order_by(ExamDomain.number)
        )
        .scalars()
        .all()
    )
    buckets = _answer_buckets(session, user_id)
    out: list[DomainMasteryOut] = []
    for d in domains:
        b = buckets.get(d.id, {"answered": 0, "correct": 0, "time_ms": 0})
        ans = b["answered"]
        cor = b["correct"]
        acc = round(cor / ans, 4) if ans else 0.0
        out.append(
            DomainMasteryOut(
                domain_id=d.id,
                number=d.number,
                name=d.name,
                weight_pct=d.weight_pct,
                answered=ans,
                correct=cor,
                accuracy=acc,
                avg_time_ms=round(b["time_ms"] / ans) if ans else 0,
                mastery_level=_mastery_from_accuracy(acc).value,
            )
        )
    return out


def trend(session: Session, *, user_id, window_days: int) -> TrendOut:
    """Daily accuracy trend over the last ``window_days`` days.

    ``window_days`` must be 30 or 90; anything else raises ``ValueError``.
    Returns one TrendPoint per active UTC day, sorted ascending by date.
    Empty user -> ``points=[]``.
    """
    if window_days not in _TREND_WINDOWS:
        raise ValueError(f"window_days must be one of {_TREND_WINDOWS}")
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = _answer_rows(session, user_id, since=since)
    by_day: dict[date, dict] = defaultdict(
        lambda: {"answered": 0, "correct": 0}
    )
    for _qid, is_correct, _tms, answered_at in rows:
        day = answered_at.astimezone(timezone.utc).date()
        by_day[day]["answered"] += 1
        if is_correct:
            by_day[day]["correct"] += 1
    points: list[TrendPoint] = []
    for day in sorted(by_day):
        b = by_day[day]
        points.append(
            TrendPoint(
                date=day,
                answered=b["answered"],
                correct=b["correct"],
                accuracy=round(b["correct"] / b["answered"], 4),
            )
        )
    return TrendOut(window_days=window_days, points=points)


def weak_areas(session: Session, *, user_id) -> WeakAreasOut:
    """Weak domains and knowledge points for ``user_id``.

    A domain/KP is "weak" when ``answered >= 3`` AND ``accuracy < 0.6``.
    Both lists are sorted by accuracy ascending and capped (8 domains,
    10 knowledge points).
    """
    buckets = _answer_buckets(session, user_id)
    # Resolve domain id -> name for labels (only when there is data).
    dom_rows = (
        session.execute(select(ExamDomain.id, ExamDomain.name)).all()
        if buckets
        else []
    )
    dom_name = {r[0]: r[1] for r in dom_rows}
    weak_d: list[WeakAreaOut] = []
    for dom_id, b in buckets.items():
        ans = b["answered"]
        if ans < _WEAK_MIN_ANSWERED:
            continue
        acc = b["correct"] / ans
        if acc < _WEAK_ACC:
            weak_d.append(
                WeakAreaOut(
                    domain_id=dom_id,
                    knowledge_point_id=None,
                    label=dom_name.get(dom_id, str(dom_id)),
                    answered=ans,
                    correct=b["correct"],
                    accuracy=round(acc, 4),
                )
            )
    weak_d.sort(key=lambda w: w.accuracy)

    # Knowledge points: bucket the merged answer rows by their KP mapping.
    rows = _answer_rows(session, user_id)
    qids = {r[0] for r in rows}
    kp_map = (
        dict(
            session.execute(
                select(
                    QuestionMapping.question_id,
                    QuestionMapping.knowledge_point_id,
                ).where(
                    QuestionMapping.question_id.in_(qids),
                    QuestionMapping.knowledge_point_id.is_not(None),
                )
            ).all()
        )
        if qids
        else {}
    )
    kp_ids = {v for v in kp_map.values() if v is not None}
    kp_name = (
        {
            r[0]: r[1]
            for r in session.execute(
                select(KnowledgePoint.id, KnowledgePoint.name).where(
                    KnowledgePoint.id.in_(kp_ids)
                )
            ).all()
        }
        if kp_ids
        else {}
    )
    kp_buckets: dict = defaultdict(lambda: {"answered": 0, "correct": 0})
    for qid, is_correct, _tms, _at in rows:
        kp = kp_map.get(qid)
        if kp is None:
            continue
        b = kp_buckets[kp]
        b["answered"] += 1
        if is_correct:
            b["correct"] += 1
    weak_k: list[WeakAreaOut] = []
    for kp_id, b in kp_buckets.items():
        ans = b["answered"]
        if ans < _WEAK_MIN_ANSWERED:
            continue
        acc = b["correct"] / ans
        if acc < _WEAK_ACC:
            weak_k.append(
                WeakAreaOut(
                    domain_id=None,
                    knowledge_point_id=kp_id,
                    label=kp_name.get(kp_id, str(kp_id)),
                    answered=ans,
                    correct=b["correct"],
                    accuracy=round(acc, 4),
                )
            )
    weak_k.sort(key=lambda w: w.accuracy)
    return WeakAreasOut(
        weak_domains=weak_d[:_MAX_WEAK_DOMAINS],
        weak_knowledge_points=weak_k[:_MAX_WEAK_KPS],
    )


def error_type_breakdown(session: Session, *, user_id) -> ErrorTypeOut:
    """Distribution of error types across the user's wrong answers.

    Wrong answers = answer rows with ``is_correct is False``. Each wrong
    question's ``UserQuestionState.error_type`` (if any) classifies it.
    ``total_wrong_classified`` counts wrong answers that HAVE a non-null
    error_type. The distribution covers the 5 enum types that occur plus
    an "unclassified" (None) bucket (always present).
    """
    rows = _answer_rows(session, user_id)
    wrong_qids = {r[0] for r in rows if r[1] is False}
    et_map = (
        dict(
            session.execute(
                select(
                    UserQuestionState.question_id, UserQuestionState.error_type
                ).where(
                    UserQuestionState.user_id == user_id,
                    UserQuestionState.question_id.in_(wrong_qids),
                )
            ).all()
        )
        if wrong_qids
        else {}
    )
    counts: dict = defaultdict(int)
    classified = 0
    for qid in wrong_qids:
        et = et_map.get(qid)
        counts[et.value if et is not None else None] += 1
        if et is not None:
            classified += 1
    # Ordered: the 5 enum types (only those with occurrences) then None.
    order = [e.value for e in ErrorType] + [None]
    distribution = [
        ErrorTypeBreakdown(error_type=k, count=counts.get(k, 0))
        for k in order
        if counts.get(k, 0) > 0 or k is None
    ]
    return ErrorTypeOut(total_wrong_classified=classified, distribution=distribution)


def recommendation(
    session: Session, *, user_id, blueprint
) -> ReviewRecommendationOut:
    """Review recommendation for ``user_id`` given the current ``blueprint``.

    ``blueprint=None`` -> graceful degradation (focus_domain=None, empty
    lists, rationale string). Otherwise:
      - focus_domain = weakest domain (first in weak_domains, or None)
      - wrong_to_review = wrong questions not yet mastered
      - next_practice_question_ids = <=10 questions from weak areas,
        least-recently-practiced first, excluding mastered AND soft-deleted
        questions.
    """
    if blueprint is None:
        return ReviewRecommendationOut(
            focus_domain=None,
            wrong_to_review=[],
            next_practice_question_ids=[],
            rationale="No current exam blueprint configured.",
        )
    wa = weak_areas(session, user_id=user_id)
    focus = wa.weak_domains[0] if wa.weak_domains else None
    rows = _answer_rows(session, user_id)
    wrong_qids = [r[0] for r in rows if r[1] is False]
    states = (
        session.execute(
            select(UserQuestionState).where(
                UserQuestionState.user_id == user_id,
                UserQuestionState.question_id.in_(wrong_qids),
            )
        ).scalars().all()
        if wrong_qids
        else []
    )
    by_q = {s.question_id: s for s in states}
    wrong_to_review = [
        qid
        for qid in wrong_qids
        if by_q.get(qid) is None
        or by_q[qid].mastery_level != MasteryLevel.mastered
    ]
    # next-practice candidates: questions whose domain OR knowledge point is
    # weak. Compute the weak-question-id set directly from wa + QuestionMapping
    # so the join stays in one place (no separate helper needed).
    weak_dom_ids = {w.domain_id for w in wa.weak_domains}
    weak_kp_ids = {w.knowledge_point_id for w in wa.weak_knowledge_points}
    qid_dom = dict(
        session.execute(
            select(QuestionMapping.question_id, QuestionMapping.domain_id)
        ).all()
    )
    qid_kp = dict(
        session.execute(
            select(
                QuestionMapping.question_id, QuestionMapping.knowledge_point_id
            )
        ).all()
    )
    weak_qids = {
        qid
        for qid in {r[0] for r in rows}
        if qid_dom.get(qid) in weak_dom_ids or qid_kp.get(qid) in weak_kp_ids
    }
    mastered_qids = {
        s.question_id for s in states if s.mastery_level == MasteryLevel.mastered
    }
    # Exclude soft-deleted questions: next-practice must point at live rows.
    live_qids = (
        {
            r[0]
            for r in session.execute(
                select(Question.id).where(
                    Question.id.in_(weak_qids), not_deleted(Question)
                )
            ).all()
        }
        if weak_qids
        else set()
    )
    candidates = [
        (qid, at)
        for qid, _cor, _tms, at in rows
        if qid in live_qids and qid not in mastered_qids
    ]
    # Distinct question, earliest answered_at wins (least-recently-practiced).
    earliest: dict = {}
    for qid, at in candidates:
        if qid not in earliest or at < earliest[qid]:
            earliest[qid] = at
    ordered = sorted(earliest.items(), key=lambda kv: kv[1])
    next_ids = [qid for qid, _at in ordered[:_MAX_NEXT_PRACTICE]]
    rationale = (
        f"Focus on your weakest domain ({focus.label}) and revisit "
        f"{len(wrong_to_review)} unmastered wrong questions."
        if focus
        else "No weak areas detected — keep practicing to maintain mastery."
    )
    return ReviewRecommendationOut(
        focus_domain=focus,
        wrong_to_review=sorted(wrong_to_review),
        next_practice_question_ids=next_ids,
        rationale=rationale,
    )


def personal_report(session: Session, *, user_id, blueprint) -> PersonalReportOut:
    """Composite personal report: dashboard + domain mastery + 30d trend +
    weak areas + error-type breakdown + recommendation.

    ``generated_at`` is ``datetime.now(timezone.utc)`` at call time.
    """
    return PersonalReportOut(
        generated_at=datetime.now(timezone.utc),
        dashboard=dashboard(session, user_id=user_id),
        domains=domain_mastery(session, user_id=user_id, blueprint=blueprint),
        trend_30d=trend(session, user_id=user_id, window_days=30),
        weak_areas=weak_areas(session, user_id=user_id),
        error_types=error_type_breakdown(session, user_id=user_id),
        recommendation=recommendation(
            session, user_id=user_id, blueprint=blueprint
        ),
    )
