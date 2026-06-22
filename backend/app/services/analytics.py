"""Analytics service — dashboard, domain mastery, trend (sub-project H1, Task 4).

Read-only service: all queries are scoped to a single ``user_id`` and never
commit (the router layer commits / doesn't-commit as appropriate for GETs).
Empty users degrade gracefully to 200 zero/empty responses.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import MasteryLevel
from app.models.exam import ExamAnswer
from app.models.practice import PracticeAnswer
from app.models.question import QuestionMapping
from app.models.taxonomy import ExamBlueprint, ExamDomain
from app.schemas.analytics import (
    DashboardOut,
    DomainMasteryOut,
    TrendOut,
    TrendPoint,
)

# Allowed trend windows (PRD spec — anything else is a programmer error).
_TREND_WINDOWS = (30, 90)


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
