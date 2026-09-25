"""Paper (试卷) service — PRD v1.4 FR-PAPER.

A paper session reuses the existing PracticeSession / ExamSession machinery:
``config["question_ids"]`` carries the paper's fixed order, so delivery,
judging, snapshots, and reports all work unchanged. Exam-mode paper sessions
set ``config["scoring"]="paper"`` which switches the report to raw per-question
scoring (FR-PAPER-06).
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.queries import not_deleted
from app.models.enums import (
    AuditAction,
    ExamSessionKind,
    ExamSessionStatus,
    PaperStatus,
    PracticeSessionStatus,
    QuestionStatus,
    QuestionType,
)
from app.models.exam import ExamSession
from app.models.paper import Paper, PaperQuestion
from app.models.practice import PracticeSession
from app.models.taxonomy import ExamBlueprint
from app.services.audit import log_audit
from app.services.errors import NotFound, ValidationError
from app.services.i18n import resolve_mode

_PAPER_PASS_RATIO = 0.6


def _load_paper(session: Session, paper_id, *, org_id, published_only=True) -> Paper:
    paper = session.get(Paper, paper_id)
    if (
        paper is None
        or paper.deleted_at is not None
        or paper.organization_id != org_id
        or (published_only and paper.status != PaperStatus.published)
    ):
        # Never reveal cross-tenant / non-published papers (404, FR-CLIENT-06).
        raise NotFound(f"paper {paper_id} not found")
    return paper


def list_papers(
    session: Session, *, org_id, user_id=None, include_unpublished=False
) -> tuple[list[dict], int]:
    stmt = select(Paper).where(Paper.organization_id == org_id, not_deleted(Paper))
    if not include_unpublished:
        stmt = stmt.where(Paper.status == PaperStatus.published)
    stmt = stmt.order_by(Paper.created_at.asc())
    papers = list(session.execute(stmt).scalars().all())

    # Caller's attempt stats (per paper): practice attempts + finished exams
    # with best raw score.
    practice_counts: dict = {}
    exam_stats: dict = {}
    if user_id is not None and papers:
        paper_ids = [p.id for p in papers]
        for ps in session.execute(
            select(PracticeSession).where(
                PracticeSession.user_id == user_id,
                PracticeSession.organization_id == org_id,
            )
        ).scalars().all():
            pid = (ps.config or {}).get("paper_id")
            if pid and uuid.UUID(pid) in paper_ids:
                practice_counts[uuid.UUID(pid)] = (
                    practice_counts.get(uuid.UUID(pid), 0) + 1
                )
        for es in session.execute(
            select(ExamSession).where(
                ExamSession.user_id == user_id,
                ExamSession.organization_id == org_id,
                ExamSession.status.in_([
                    ExamSessionStatus.completed,
                    ExamSessionStatus.auto_submitted,
                ]),
            )
        ).scalars().all():
            pid = (es.config or {}).get("paper_id")
            if not pid or uuid.UUID(pid) not in paper_ids:
                continue
            scores = exam_stats.setdefault(
                uuid.UUID(pid), {"attempts": 0, "best_score": None}
            )
            scores["attempts"] += 1
            best = scores["best_score"]
            scaled = _paper_raw_score(es)
            if best is None or scaled > best:
                scores["best_score"] = scaled

    items = [
        {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "duration_minutes": p.duration_minutes,
            "total_score": p.total_score,
            "question_count": p.question_count,
            "status": p.status.value,
            "domain_number": p.domain_number,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "attempts": practice_counts.get(p.id, 0)
            + exam_stats.get(p.id, {"attempts": 0})["attempts"],
            "best_score": exam_stats.get(p.id, {}).get("best_score"),
            "max_score": p.total_score,
        }
        for p in papers
    ]
    return items, len(items)


def get_paper(
    session: Session, *, paper_id, org_id, user_id=None, published_only=True
) -> dict:
    paper = _load_paper(session, paper_id, org_id=org_id, published_only=published_only)
    type_counts: dict[str, int] = {}
    questions = []
    from app.models.question import Question

    rows = list(
        session.execute(
            select(
                Question.question_type,
                PaperQuestion.position,
                PaperQuestion.score,
                Question.id,
            )
            .join(PaperQuestion, PaperQuestion.question_id == Question.id)
            .where(PaperQuestion.paper_id == paper.id)
            .order_by(PaperQuestion.position)
        ).all()
    )
    for qtype, position, score, qid in rows:
        key = qtype.value if hasattr(qtype, "value") else str(qtype)
        type_counts[key] = type_counts.get(key, 0) + 1
        questions.append({
            "position": position,
            "question_id": str(qid),
            "question_type": key,
            "score": score,
        })
    return {
        "id": str(paper.id),
        "name": paper.name,
        "description": paper.description,
        "duration_minutes": paper.duration_minutes,
        "total_score": paper.total_score,
        "question_count": paper.question_count,
        "status": paper.status.value,
        "domain_number": paper.domain_number,
        "type_counts": type_counts,
        "questions": questions,
        "created_at": paper.created_at.isoformat() if paper.created_at else None,
    }


def _paper_questions(session: Session, paper: Paper):
    return sorted(paper.questions, key=lambda pq: pq.position)


def _paper_raw_score(es: ExamSession) -> int:
    """Best-effort raw score for a finished paper exam (from config + answers)."""
    cfg = es.config or {}
    scores = list(cfg.get("scores") or [])
    correct = cfg.get("paper_correct")
    if correct is None:
        return es.correct_count or 0
    return int(correct)


def create_paper_session(
    session: Session, *, paper_id, org_id, actor_id, mode: str, language_mode=None
):
    """FR-PAPER-04: one-click 练习/考试 on a paper.

    practice -> PracticeSession over the paper's fixed order.
    exam     -> ExamSession (kind fixed) with paper scoring + paper duration.
    """
    if mode not in ("practice", "exam"):
        raise ValidationError("mode must be practice or exam")
    paper = _load_paper(session, paper_id, org_id=org_id)
    pqs = _paper_questions(session, paper)
    if not pqs:
        raise ValidationError("paper has no questions")
    question_ids = [str(pq.question_id) for pq in pqs]
    scores = [pq.score for pq in pqs]
    resolved_mode = resolve_mode(session, actor_id, language_mode)

    if mode == "practice":
        ps = PracticeSession(
            user_id=actor_id,
            organization_id=org_id,
            status=PracticeSessionStatus.in_progress,
            total_questions=len(question_ids),
            config={
                "paper_id": str(paper.id),
                "paper_name": paper.name,
                "subset": "paper",
                "order_mode": "sequential",
                "count": len(question_ids),
                "language_mode": resolved_mode,
                "shuffle_options": False,
                "question_ids": question_ids,
            },
        )
        session.add(ps)
        session.flush()
        log_audit(
            session, action=AuditAction.edit, actor_id=actor_id,
            organization_id=org_id, entity_type="practice_session",
            entity_id=str(ps.id),
            details={"paper_id": str(paper.id), "mode": "practice"},
        )
        return ps

    # exam mode — blueprint_id is a formal FK (assembly never consults it for
    # papers); the current blueprint must exist to satisfy the NOT NULL.
    bp = session.execute(
        select(ExamBlueprint).where(ExamBlueprint.is_current.is_(True))
    ).scalars().first()
    if bp is None:
        raise ValidationError("no current exam blueprint configured")
    started = datetime.now(timezone.utc)
    duration = paper.duration_minutes or 60
    deadline = started + timedelta(minutes=duration)
    total_score = paper.total_score or sum(scores)
    config = {
        "paper_id": str(paper.id),
        "paper_name": paper.name,
        "scoring": "paper",
        "count": len(question_ids),
        "question_ids": question_ids,
        "scores": scores,
        "deadline_at": deadline.isoformat(),
        "max_score": total_score,
        "passing_score": round(total_score * _PAPER_PASS_RATIO),
        "duration_minutes": duration,
        "language_mode": resolved_mode,
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
        details={"paper_id": str(paper.id), "mode": "exam", "scoring": "paper"},
    )
    return es


def list_paper_sessions(
    session: Session, *, paper_id, user_id, org_id
) -> list[dict]:
    _load_paper(session, paper_id, org_id=org_id)
    out: list[dict] = []
    for ps in session.execute(
        select(PracticeSession)
        .where(PracticeSession.user_id == user_id)
        .order_by(PracticeSession.started_at.desc())
        .limit(50)
    ).scalars().all():
        if (ps.config or {}).get("paper_id") != str(paper_id):
            continue
        out.append({
            "id": str(ps.id),
            "kind": "practice",
            "status": ps.status.value,
            "total_questions": ps.total_questions,
            "correct_count": ps.correct_count,
            "started_at": ps.started_at.isoformat() if ps.started_at else None,
            "ended_at": ps.ended_at.isoformat() if ps.ended_at else None,
        })
    for es in session.execute(
        select(ExamSession)
        .where(ExamSession.user_id == user_id)
        .order_by(ExamSession.started_at.desc())
        .limit(50)
    ).scalars().all():
        if (es.config or {}).get("paper_id") != str(paper_id):
            continue
        out.append({
            "id": str(es.id),
            "kind": "exam",
            "status": es.status.value,
            "total_questions": es.total_questions,
            "correct_count": es.correct_count,
            "started_at": es.started_at.isoformat() if es.started_at else None,
            "ended_at": es.ended_at.isoformat() if es.ended_at else None,
        })
    out.sort(key=lambda x: x["started_at"] or "", reverse=True)
    return out
