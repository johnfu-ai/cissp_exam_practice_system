"""Fixed exam service (sub-project F).

Owns fixed-count exam session creation with domain-weighted auto-assembly
from the current ExamBlueprint, timed feedback-free delivery with lazy
auto-submit, revisable answer submission (judged from snapshot), finish +
report, unified post-exam review, and history/trend.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.queries import not_deleted
from app.models.enums import (
    AuditAction,
    ExamSessionKind,
    ExamSessionStatus,
    QuestionStatus,
)
from app.models.exam import ExamAnswer, ExamSession
from app.models.question import Explanation, Question, QuestionMapping, QuestionOption
from app.models.taxonomy import ExamBlueprint, ExamDomain
from app.schemas.exam import (
    DomainPerformance,
    ExamAnswerAck,
    ExamAnswerIn,
    ExamCreateIn,
    ExamHistoryItemOut,
    ExamReportOut,
    ReviewItemOut,
    WrongQuestion,
)
from app.services.audit import log_audit
from app.services.snapshot import snapshot_question


class ValidationError(ValueError):
    pass


class NotFound(LookupError):
    pass


class ConflictError(ValueError):
    pass


def _as_create_in(payload) -> ExamCreateIn:
    if isinstance(payload, ExamCreateIn):
        return payload
    return ExamCreateIn(**(payload or {}))


def _current_blueprint(session: Session) -> ExamBlueprint:
    bp = session.execute(
        select(ExamBlueprint).where(ExamBlueprint.is_current.is_(True))
    ).scalars().first()
    if bp is None:
        raise ValidationError("no current exam blueprint configured")
    return bp


def _allocate(count: int, weights: list[int]) -> list[int]:
    """Largest-remainder allocation: per-domain targets summing exactly to count."""
    raw = [count * w / 100 for w in weights]
    floors = [int(r) for r in raw]
    leftover = count - sum(floors)
    if leftover > 0:
        order = sorted(
            range(len(raw)),
            key=lambda i: raw[i] - floors[i],
            reverse=True,
        )
        for i in range(leftover):
            floors[order[i]] += 1
    return floors


def _domain_question_ids(
    session: Session, *, org_id, domain_id
) -> list[uuid.UUID]:
    return [
        row[0]
        for row in session.execute(
            select(QuestionMapping.question_id)
            .where(
                QuestionMapping.domain_id == domain_id,
                QuestionMapping.question_id.in_(
                    select(Question.id).where(
                        Question.organization_id == org_id,
                        Question.status == QuestionStatus.published,
                        not_deleted(Question),
                    )
                ),
            )
            .order_by(func.random())
        ).all()
    ]


def _assemble(
    session: Session, *, org_id, blueprint: ExamBlueprint, count: int
) -> list[uuid.UUID]:
    domains = list(
        session.execute(
            select(ExamDomain)
            .where(ExamDomain.blueprint_id == blueprint.id)
            .order_by(ExamDomain.number)
        ).scalars().all()
    )
    if not domains:
        raise ValidationError("current blueprint has no domains configured")
    targets = _allocate(count, [d.weight_pct for d in domains])
    pools = {
        d.id: _domain_question_ids(session, org_id=org_id, domain_id=d.id)
        for d in domains
    }
    taken: dict[uuid.UUID, list[uuid.UUID]] = {d.id: [] for d in domains}
    for d, t in zip(domains, targets):
        taken[d.id] = pools[d.id][:t]
    shortfall = count - sum(len(v) for v in taken.values())
    while shortfall > 0:
        progressed = False
        for d in domains:
            if shortfall <= 0:
                break
            have = len(taken[d.id])
            pool = pools[d.id]
            if have < len(pool):
                taken[d.id].append(pool[have])
                shortfall -= 1
                progressed = True
        if not progressed:
            break
    if shortfall > 0:
        raise ValidationError(
            f"not enough published questions to assemble a {count}-question exam"
        )
    all_ids = [qid for d in domains for qid in taken[d.id]]
    random.shuffle(all_ids)
    return all_ids


def create_session(
    session: Session, *, org_id, actor_id, payload
) -> ExamSession:
    body = _as_create_in(payload)
    bp = _current_blueprint(session)
    count = body.count if body.count else bp.max_items
    if count < bp.min_items:
        count = bp.min_items
    if count > bp.max_items:
        count = bp.max_items
    question_ids = _assemble(session, org_id=org_id, blueprint=bp, count=count)
    if not question_ids:
        raise ValidationError(
            f"not enough published questions to assemble a {count}-question exam"
        )
    started = datetime.now(timezone.utc)
    deadline = started + timedelta(minutes=bp.duration_minutes)
    config = {
        "count": len(question_ids),
        "question_ids": [str(q) for q in question_ids],
        "deadline_at": deadline.isoformat(),
        "max_score": bp.max_score,
        "passing_score": bp.passing_score,
        "duration_minutes": bp.duration_minutes,
    }
    es = ExamSession(
        user_id=actor_id,
        organization_id=org_id,
        blueprint_id=bp.id,
        session_kind=ExamSessionKind.fixed,
        status=ExamSessionStatus.in_progress,
        total_questions=len(question_ids),
        correct_count=0,
        config=config,
    )
    session.add(es)
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=actor_id, organization_id=org_id,
        entity_type="exam_session", entity_id=str(es.id),
        details={"total_questions": len(question_ids), "kind": "fixed"},
    )
    return es


def _load_session(session: Session, session_id, user_id) -> ExamSession:
    es = session.get(ExamSession, session_id)
    if es is None or es.user_id != user_id:
        raise NotFound(f"exam session {session_id} not found")
    return es


def _deadline(es: ExamSession) -> datetime:
    dl = datetime.fromisoformat(es.config.get("deadline_at"))
    if dl.tzinfo is None:
        dl = dl.replace(tzinfo=timezone.utc)
    return dl


def _time_remaining_ms(es: ExamSession) -> int:
    return max(
        0, int((_deadline(es) - datetime.now(timezone.utc)).total_seconds() * 1000)
    )


def _auto_submit_if_expired(session: Session, es: ExamSession) -> bool:
    if es.status != ExamSessionStatus.in_progress:
        return False
    if datetime.now(timezone.utc) < _deadline(es):
        return False
    es.status = ExamSessionStatus.auto_submitted
    es.ended_at = _deadline(es)
    session.flush()
    return True


def _options_for(session: Session, question_id) -> list[QuestionOption]:
    return list(
        session.execute(
            select(QuestionOption)
            .where(QuestionOption.question_id == question_id)
            .order_by(QuestionOption.order_index)
        ).scalars().all()
    )


def _judge(snapshot: dict, selected: list[int]) -> bool:
    correct_indexes = [
        o["order_index"] for o in snapshot["options"] if o["is_correct"]
    ]
    return set(selected) == set(correct_indexes)


def get_question_at(session: Session, *, session_id, position: int, user_id) -> dict:
    es = _load_session(session, session_id, user_id)
    if _auto_submit_if_expired(session, es) or es.status != ExamSessionStatus.in_progress:
        raise ConflictError("exam session is not in progress")
    qids = es.config.get("question_ids", [])
    if position < 0 or position >= len(qids):
        raise ValidationError("position out of range")
    question = session.get(Question, uuid.UUID(qids[position]))
    if question is None or question.deleted_at is not None:
        raise NotFound("question no longer available")
    options = _options_for(session, question.id)
    started = es.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    elapsed_ms = int(
        (datetime.now(timezone.utc) - started).total_seconds() * 1000
    )
    prev = session.execute(
        select(ExamAnswer).where(
            ExamAnswer.session_id == es.id,
            ExamAnswer.question_id == question.id,
        )
    ).scalars().first()
    return {
        "session_id": str(es.id),
        "position": position,
        "total": len(qids),
        "question_id": str(question.id),
        "stem": question.stem,
        "question_type": question.question_type.value,
        "options": [
            {
                "id": str(o.id),
                "order_index": o.order_index,
                "content": o.content,
                "content_format": o.content_format.value,
            }
            for o in options
        ],
        "elapsed_ms": elapsed_ms,
        "time_remaining_ms": _time_remaining_ms(es),
        "previous_answer": (
            {"selected": prev.user_answer.get("selected")} if prev else None
        ),
    }


def submit_answer(session: Session, *, session_id, user_id, payload) -> ExamAnswerAck:
    body = payload if isinstance(payload, ExamAnswerIn) else ExamAnswerIn(**payload)
    es = _load_session(session, session_id, user_id)
    if _auto_submit_if_expired(session, es) or es.status != ExamSessionStatus.in_progress:
        raise ConflictError("exam session is not in progress")
    qids = es.config.get("question_ids", [])
    if body.position < 0 or body.position >= len(qids):
        raise ValidationError("position out of range")
    question_id = uuid.UUID(qids[body.position])
    question = session.get(Question, question_id)
    if question is None or question.deleted_at is not None:
        raise NotFound("question no longer available")
    options = _options_for(session, question_id)
    snap = snapshot_question(question, options)
    is_correct = _judge(snap, body.selected)
    now = datetime.now(timezone.utc)
    started = body.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    time_spent_ms = max(0, int((now - started).total_seconds() * 1000))
    existing = session.execute(
        select(ExamAnswer).where(
            ExamAnswer.session_id == es.id,
            ExamAnswer.question_id == question_id,
        )
    ).scalars().first()
    if existing is None:
        existing = ExamAnswer(
            session_id=es.id, user_id=user_id, question_id=question_id,
        )
        session.add(existing)
    existing.question_snapshot = snap
    existing.options_snapshot = snap["options"]
    existing.user_answer = {"selected": body.selected}
    existing.is_correct = is_correct
    existing.time_spent_ms = time_spent_ms
    existing.answered_at = now
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=user_id,
        organization_id=es.organization_id, entity_type="exam_answer",
        entity_id=str(existing.id), details={"is_correct": is_correct},
    )
    return ExamAnswerAck(
        position=body.position, saved=True,
        time_remaining_ms=_time_remaining_ms(es),
    )


def finish_session(session, *, session_id, user_id):
    raise NotImplementedError


def get_report(session, *, session_id, user_id):
    raise NotImplementedError


def get_review(session, *, session_id, user_id):
    raise NotImplementedError


def list_history(session, *, user_id):
    raise NotImplementedError
