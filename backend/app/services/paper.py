"""Paper (试卷) service — PRD v1.4 FR-PAPER.

A paper session reuses the existing PracticeSession / ExamSession machinery:
``config["question_ids"]`` carries the paper's fixed order, so delivery,
judging, snapshots, and reports all work unchanged. Exam-mode paper sessions
set ``config["scoring"]="paper"`` which switches the report to raw per-question
scoring (FR-PAPER-06).
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
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
from app.models.exam import ExamAnswer, ExamSession
from app.models.paper import Paper, PaperQuestion
from app.models.practice import PracticeAnswer, PracticeSession
from app.models.taxonomy import ExamBlueprint
from app.services.audit import log_audit
from app.services.errors import ConflictError, NotFound, ValidationError
from app.services.i18n import resolve_mode
from app.services.practice import practice_elapsed_seconds

_PAPER_PASS_RATIO = 0.6


def list_banks(session: Session, *, org_id) -> list[dict]:
    """FR-PAPER-10: learner-facing free-practice banks — datasets that carry
    published questions. Datasets whose questions all sit in draft (e.g. a
    paper-only import) are covered by their paper cards and are omitted."""
    from app.models.etl import EtlDataset, QuestionExternalKey
    from app.models.question import Question

    out: list[dict] = []
    for ds in session.execute(
        select(EtlDataset)
        .where(EtlDataset.organization_id == org_id)
        .order_by(EtlDataset.created_at.asc())
    ).scalars().all():
        published = session.execute(
            select(func.count())
            .select_from(Question)
            .join(
                QuestionExternalKey,
                QuestionExternalKey.question_id == Question.id,
            )
            .where(
                QuestionExternalKey.dataset_slug == ds.slug,
                Question.status == QuestionStatus.published,
                not_deleted(Question),
            )
        ).scalar_one()
        if published == 0:
            continue
        has_papers = session.execute(
            select(func.count())
            .select_from(Paper)
            .where(
                Paper.dataset_slug == ds.slug,
                Paper.organization_id == org_id,
                Paper.status == PaperStatus.published,
                not_deleted(Paper),
            )
        ).scalar_one() > 0
        out.append({
            "dataset_slug": ds.slug,
            "name": ds.name,
            "question_count": published,
            "languages": list(ds.languages or []),
            "has_papers": has_papers,
        })
    return out


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

    # Caller's attempt stats (per paper): FINISHED practice attempts
    # (v1.7 — in-progress/abandoned don't count) + finished exams with best
    # raw score.
    practice_counts: dict = {}
    exam_stats: dict = {}
    if user_id is not None and papers:
        paper_ids = [p.id for p in papers]
        for ps in session.execute(
            select(PracticeSession).where(
                PracticeSession.user_id == user_id,
                PracticeSession.organization_id == org_id,
                PracticeSession.status == PracticeSessionStatus.completed,
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


def _abandon_in_progress(session: Session, *, paper_id, user_id, org_id, mode: str):
    """v1.7 FR-PAPER-12: 「重新开始」— abandon the user's previous in-progress
    sessions for the SAME paper+mode so they never linger in the resume list
    or inflate attempt counts. The other mode is untouched."""
    if mode == "practice":
        for ps in session.execute(
            select(PracticeSession).where(
                PracticeSession.user_id == user_id,
                PracticeSession.organization_id == org_id,
                PracticeSession.status == PracticeSessionStatus.in_progress,
            )
        ).scalars().all():
            if (ps.config or {}).get("paper_id") != str(paper_id):
                continue
            ps.status = PracticeSessionStatus.abandoned
            ps.ended_at = datetime.now(timezone.utc)
    else:
        for es in session.execute(
            select(ExamSession).where(
                ExamSession.user_id == user_id,
                ExamSession.organization_id == org_id,
                ExamSession.status == ExamSessionStatus.in_progress,
            )
        ).scalars().all():
            if (es.config or {}).get("paper_id") != str(paper_id):
                continue
            es.status = ExamSessionStatus.aborted
            es.ended_at = datetime.now(timezone.utc)
    session.flush()


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
    # v1.7 FR-PAPER-12: 「重新开始」— abandon the caller's previous
    # in-progress session for the SAME paper+mode (other mode untouched)
    _abandon_in_progress(
        session, paper_id=paper.id, user_id=actor_id, org_id=org_id, mode=mode
    )
    started = datetime.now(timezone.utc)

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
                # v1.7 active-time clock (中断即停表 — no wall-clock fallback)
                "elapsed_seconds": 0,
                "last_seen_at": started.isoformat(),
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
    duration = paper.duration_minutes or 60
    budget = duration * 60
    deadline = started + timedelta(seconds=budget)
    total_score = paper.total_score or sum(scores)
    config = {
        "paper_id": str(paper.id),
        "paper_name": paper.name,
        "scoring": "paper",
        "count": len(question_ids),
        "question_ids": question_ids,
        "scores": scores,
        "deadline_at": deadline.isoformat(),
        # v1.7 active-time budget: countdown = budget − accumulated active
        # time; time away from the player does not consume it
        "duration_budget_seconds": budget,
        "elapsed_seconds": 0,
        "last_seen_at": started.isoformat(),
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


def _paper_exam_score(cfg: dict, qids: list, answered_correct_ids: set) -> int:
    """FR-PAPER-14: raw paper score for an exam attempt — mirrors the report
    (`_build_paper_report`): per-question points for correct answers."""
    scores = list(cfg.get("scores") or [1] * len(qids))
    total = 0
    for position, qid in enumerate(qids):
        if uuid.UUID(qid) in answered_correct_ids:
            total += scores[position] if position < len(scores) else 1
    return total


def _attempt_duration_seconds(cfg: dict, started, ended, *, finished: bool) -> int | None:
    """v1.7: 用时 = active accumulated time once the session is finished (no
    away-grace appended); wall clock only for sessions without a heartbeat
    clock (legacy) or still in progress."""
    if finished and cfg.get("last_seen_at") and cfg.get("elapsed_seconds") is not None:
        return int(cfg["elapsed_seconds"])
    return _duration_seconds(started, ended)


def _duration_seconds(started, ended) -> int | None:
    if started is None or ended is None:
        return None
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if ended.tzinfo is None:
        ended = ended.replace(tzinfo=timezone.utc)
    return max(0, int((ended - started).total_seconds()))


def list_paper_sessions(
    session: Session, *, paper_id, user_id, org_id
) -> list[dict]:
    """FR-PAPER-14: the caller's attempt history for one paper. Exam rows
    carry the raw point score / pass verdict; practice rows leave them null."""
    _load_paper(session, paper_id, org_id=org_id)
    out: list[dict] = []

    practice_rows = [
        ps for ps in session.execute(
            select(PracticeSession)
            .where(PracticeSession.user_id == user_id)
            .order_by(PracticeSession.started_at.desc())
            .limit(50)
        ).scalars().all()
        if (ps.config or {}).get("paper_id") == str(paper_id)
    ]
    exam_rows = [
        es for es in session.execute(
            select(ExamSession)
            .where(ExamSession.user_id == user_id)
            .order_by(ExamSession.started_at.desc())
            .limit(50)
        ).scalars().all()
        if (es.config or {}).get("paper_id") == str(paper_id)
    ]

    # one bulk answers query per kind (no per-session N+1)
    practice_answer_counts: dict = {}
    if practice_rows:
        for sid, n in session.execute(
            select(PracticeAnswer.session_id, func.count())
            .where(PracticeAnswer.session_id.in_([p.id for p in practice_rows]))
            .group_by(PracticeAnswer.session_id)
        ).all():
            practice_answer_counts[sid] = n
    exam_answers: dict = {}
    if exam_rows:
        for a in session.execute(
            select(ExamAnswer).where(
                ExamAnswer.session_id.in_([e.id for e in exam_rows])
            )
        ).scalars().all():
            exam_answers.setdefault(a.session_id, []).append(a)

    for ps in practice_rows:
        out.append({
            "id": str(ps.id),
            "kind": "practice",
            "status": ps.status.value,
            "total_questions": ps.total_questions,
            "correct_count": ps.correct_count,
            "started_at": ps.started_at.isoformat() if ps.started_at else None,
            "ended_at": ps.ended_at.isoformat() if ps.ended_at else None,
            "answered": practice_answer_counts.get(ps.id, 0),
            "score": None,
            "max_score": None,
            "passed": None,
            "duration_seconds": _attempt_duration_seconds(
                ps.config or {}, ps.started_at, ps.ended_at,
                finished=ps.status == PracticeSessionStatus.completed,
            ),
        })
    for es in exam_rows:
        cfg = es.config or {}
        qids = list(cfg.get("question_ids") or [])
        answers = exam_answers.get(es.id, [])
        correct_ids = {a.question_id for a in answers if a.is_correct}
        raw = _paper_exam_score(cfg, qids, correct_ids)
        max_score = cfg.get("max_score") or (
            sum(cfg.get("scores") or []) if cfg.get("scores") else None
        )
        passing = cfg.get("passing_score") or (
            round(max_score * _PAPER_PASS_RATIO) if max_score else None
        )
        out.append({
            "id": str(es.id),
            "kind": "exam",
            "status": es.status.value,
            "total_questions": es.total_questions,
            "correct_count": es.correct_count,
            "started_at": es.started_at.isoformat() if es.started_at else None,
            "ended_at": es.ended_at.isoformat() if es.ended_at else None,
            "answered": len(answers),
            "score": raw,
            "max_score": max_score,
            "passed": (raw >= passing) if passing is not None else None,
            "duration_seconds": _attempt_duration_seconds(
                es.config or {}, es.started_at, es.ended_at,
                finished=es.status in (
                    ExamSessionStatus.completed, ExamSessionStatus.auto_submitted,
                ),
            ),
        })
    out.sort(key=lambda x: x["started_at"] or "", reverse=True)
    return out


# --- FR-PAPER-12: resume bundle -------------------------------------------------


def _positions_of(qids: list) -> dict:
    return {str(q): i for i, q in enumerate(qids)}


def session_state(session: Session, *, session_id, user_id, org_id) -> dict:
    """Resume bundle for the paper player: answer-sheet state, progress, and
    time. Accepts paper practice/exam sessions and bank (dataset) practice
    sessions; never reveals another user's session (404)."""
    ps = session.get(PracticeSession, session_id)
    if ps is not None:
        if ps.user_id != user_id or ps.organization_id != org_id:
            raise NotFound(f"session {session_id} not found")
        return _practice_state(session, ps)
    es = session.get(ExamSession, session_id)
    if es is not None:
        if es.user_id != user_id or es.organization_id != org_id:
            raise NotFound(f"session {session_id} not found")
        return _exam_state(session, es)
    raise NotFound(f"session {session_id} not found")


def _practice_state(db: Session, ps: PracticeSession) -> dict:
    cfg = ps.config or {}
    qids = list(cfg.get("question_ids") or [])
    pos_of = _positions_of(qids)
    answered: list[int] = []
    wrong: list[int] = []
    for a in db.execute(
        select(PracticeAnswer).where(PracticeAnswer.session_id == ps.id)
    ).scalars().all():
        pos = pos_of.get(str(a.question_id))
        if pos is None:
            continue
        answered.append(pos)
        if a.is_correct is False:
            wrong.append(pos)
    return {
        "session_id": str(ps.id),
        "kind": "practice",
        "status": ps.status.value,
        "paper_id": cfg.get("paper_id"),
        "paper_name": cfg.get("paper_name"),
        "total": len(qids),
        "answered_positions": sorted(answered),
        "wrong_positions": sorted(wrong),
        "elapsed_seconds": practice_elapsed_seconds(ps),
        "deadline_at": None,
    }


def _exam_state(db: Session, es: ExamSession) -> dict:
    cfg = es.config or {}
    qids = list(cfg.get("question_ids") or [])
    pos_of = _positions_of(qids)
    answered = [
        pos
        for a in db.execute(
            select(ExamAnswer).where(ExamAnswer.session_id == es.id)
        ).scalars().all()
        if (pos := pos_of.get(str(a.question_id))) is not None
    ]
    # v1.7: active-time budget model — remaining = budget − accumulated
    # active time; time away does not consume it. deadline_at is refreshed
    # to now + remaining so legacy wall-deadline clients stay correct.
    elapsed: int | None = None
    deadline_at = cfg.get("deadline_at")
    budget = cfg.get("duration_budget_seconds")
    if budget is not None:
        elapsed = practice_elapsed_seconds(es)
        if es.status == ExamSessionStatus.in_progress:
            remaining = max(0, int(budget) - elapsed)
            deadline_at = (
                datetime.now(timezone.utc) + timedelta(seconds=remaining)
            ).isoformat()
            new_cfg = dict(cfg)
            new_cfg["deadline_at"] = deadline_at
            es.config = new_cfg
            db.flush()
    return {
        "session_id": str(es.id),
        "kind": "exam",
        "status": es.status.value,
        "paper_id": cfg.get("paper_id"),
        "paper_name": cfg.get("paper_name"),
        "total": len(qids),
        "answered_positions": sorted(answered),
        # exam mode never leaks correctness to the answer sheet mid-exam
        "wrong_positions": [],
        "elapsed_seconds": elapsed,
        "duration_budget_seconds": (int(budget) if budget is not None else None),
        "deadline_at": deadline_at,
    }


def heartbeat_session(
    session: Session, *, session_id, user_id, org_id, elapsed_seconds: int
) -> dict:
    """v1.7 FR-PAPER-12: unified active-time heartbeat for every session the
    paper player hosts — paper/bank practice sessions AND paper exam
    sessions. Accumulates with the same monotonic clamp as the practice
    endpoint; for budget exams it also refreshes ``deadline_at`` to
    now + remaining (active-time semantics — away time does not count)."""
    from app.services.practice import HEARTBEAT_MAX_STEP_SECONDS

    ps, es = _load_owned(session, session_id, user_id=user_id, org_id=org_id)
    target = ps if ps is not None else es
    in_progress = (
        PracticeSessionStatus.in_progress
        if ps is not None else ExamSessionStatus.in_progress
    )
    if target.status != in_progress:
        raise ConflictError("session is not in progress")
    cfg = dict(target.config or {})
    prev = int(cfg.get("elapsed_seconds") or 0)
    cfg["elapsed_seconds"] = max(
        prev, min(int(elapsed_seconds), prev + HEARTBEAT_MAX_STEP_SECONDS)
    )
    cfg["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    if es is not None:
        budget = cfg.get("duration_budget_seconds")
        if budget is not None:
            remaining = max(0, int(budget) - cfg["elapsed_seconds"])
            cfg["deadline_at"] = (
                datetime.now(timezone.utc) + timedelta(seconds=remaining)
            ).isoformat()
    target.config = cfg
    session.flush()
    out = {
        "session_id": str(target.id),
        "elapsed_seconds": cfg["elapsed_seconds"],
    }
    if es is not None and cfg.get("duration_budget_seconds") is not None:
        out["remaining_seconds"] = max(
            0, int(cfg["duration_budget_seconds"]) - cfg["elapsed_seconds"]
        )
    return out


def list_in_progress(session: Session, *, user_id, org_id) -> list[dict]:
    """FR-PAPER-12: the caller's resumable sessions — in-progress paper
    practice/exam sessions plus bank (dataset) practice sessions, newest
    first. Plain ad-hoc practice sessions (no paper, no dataset) are omitted."""
    from app.models.etl import EtlDataset

    out: list[dict] = []
    dataset_slugs: set[str] = set()
    rows: list[tuple] = []

    for ps in session.execute(
        select(PracticeSession).where(
            PracticeSession.user_id == user_id,
            PracticeSession.organization_id == org_id,
            PracticeSession.status == PracticeSessionStatus.in_progress,
        )
    ).scalars().all():
        rows.append((ps.started_at, "practice", ps))
    for es in session.execute(
        select(ExamSession).where(
            ExamSession.user_id == user_id,
            ExamSession.organization_id == org_id,
            ExamSession.status == ExamSessionStatus.in_progress,
        )
    ).scalars().all():
        rows.append((es.started_at, "exam", es))
    rows.sort(key=lambda r: r[0] or datetime.min.replace(tzinfo=timezone.utc),
              reverse=True)

    for started, kind, s in rows:
        cfg = s.config or {}
        paper_id = cfg.get("paper_id")
        dataset_slug = cfg.get("dataset_slug")
        if not paper_id and not dataset_slug:
            continue
        if dataset_slug:
            dataset_slugs.add(dataset_slug)
        out.append({
            "session_id": str(s.id),
            "kind": kind,
            "source": "paper" if paper_id else "bank",
            "paper_id": paper_id,
            "paper_name": cfg.get("paper_name"),
            "dataset_slug": dataset_slug,
            "dataset_name": None,
            "total": len(cfg.get("question_ids") or []),
            "answered": 0,
            "started_at": started.isoformat() if started else None,
            "_model": s,
        })

    names: dict[str, str] = {}
    if dataset_slugs:
        for ds in session.execute(
            select(EtlDataset).where(
                EtlDataset.slug.in_(dataset_slugs),
                EtlDataset.organization_id == org_id,
            )
        ).scalars().all():
            names[ds.slug] = ds.name

    for entry in out:
        entry["dataset_name"] = names.get(entry["dataset_slug"])
        if entry["dataset_name"] is None and entry["dataset_slug"]:
            entry["dataset_name"] = entry["dataset_slug"]
        s = entry.pop("_model")
        if entry["kind"] == "practice":
            entry["answered"] = session.execute(
                select(func.count()).select_from(PracticeAnswer).where(
                    PracticeAnswer.session_id == s.id
                )
            ).scalar_one()
        else:
            entry["answered"] = session.execute(
                select(func.count()).select_from(ExamAnswer).where(
                    ExamAnswer.session_id == s.id
                )
            ).scalar_one()
    return out


# --- FR-PAPER-11: practice ⇄ exam mode switch -----------------------------------


def _switch_audit(session: Session, *, org_id, user_id, entity_type, entity_id,
                  switched_from, mode):
    log_audit(
        session, action=AuditAction.edit, actor_id=user_id,
        organization_id=org_id, entity_type=entity_type,
        entity_id=str(entity_id),
        details={"switched_from": str(switched_from), "mode": mode},
    )


def _load_owned(session: Session, session_id, *, user_id, org_id):
    """Fetch a practice- or exam-session by id, enforcing ownership."""
    ps = session.get(PracticeSession, session_id)
    if ps is not None:
        if ps.user_id != user_id or ps.organization_id != org_id:
            raise NotFound(f"session {session_id} not found")
        return ps, None
    es = session.get(ExamSession, session_id)
    if es is not None:
        if es.user_id != user_id or es.organization_id != org_id:
            raise NotFound(f"session {session_id} not found")
        return None, es
    raise NotFound(f"session {session_id} not found")


def switch_mode(
    session: Session, *, session_id, user_id, org_id, mode: str
) -> dict:
    """FR-PAPER-11: convert an in-progress paper session to the other mode.

    The conversion creates a NEW session of the target kind over the same
    question order, copies every existing answer (snapshots included), and
    abandons the source session. Time is preserved: practice→exam sets the
    deadline to the paper duration minus the accumulated practice time;
    exam→practice seeds the practice heartbeat clock with the exam's elapsed
    wall clock."""
    if mode not in ("practice", "exam"):
        raise ValidationError("mode must be practice or exam")
    ps, es = _load_owned(session, session_id, user_id=user_id, org_id=org_id)
    if ps is not None:
        return _switch_from_practice(
            session, ps=ps, user_id=user_id, org_id=org_id, mode=mode
        )
    return _switch_from_exam(
        session, es=es, user_id=user_id, org_id=org_id, mode=mode
    )


def _switch_from_practice(
    session: Session, *, ps: PracticeSession, user_id, org_id, mode: str
) -> dict:
    cfg = ps.config or {}
    paper_id = cfg.get("paper_id")
    if mode == "practice":
        return {"session_id": str(ps.id), "kind": "practice", "paper_id": paper_id}
    if ps.status != PracticeSessionStatus.in_progress:
        raise ConflictError("session is not in progress")
    if not paper_id:
        raise ValidationError("session is not attached to a paper")
    paper = _load_paper(session, uuid.UUID(paper_id), org_id=org_id)
    qids = [str(q) for q in (cfg.get("question_ids") or [])]
    score_of = {str(pq.question_id): pq.score for pq in paper.questions}
    scores = [score_of.get(q, 1) for q in qids]
    elapsed = practice_elapsed_seconds(ps)
    duration = paper.duration_minutes or 60
    remaining = duration * 60 - elapsed
    if remaining <= 0:
        raise ValidationError("exam time for this paper is already exhausted")

    bp = session.execute(
        select(ExamBlueprint).where(ExamBlueprint.is_current.is_(True))
    ).scalars().first()
    if bp is None:
        raise ValidationError("no current exam blueprint configured")
    now = datetime.now(timezone.utc)
    total_score = paper.total_score or sum(scores)
    es = ExamSession(
        user_id=user_id,
        organization_id=org_id,
        blueprint_id=bp.id,
        session_kind=ExamSessionKind.fixed,
        status=ExamSessionStatus.in_progress,
        total_questions=len(qids),
        correct_count=0,
        config={
            "paper_id": paper_id,
            "paper_name": paper.name,
            "scoring": "paper",
            "count": len(qids),
            "question_ids": qids,
            "scores": scores,
            "deadline_at": (now + timedelta(seconds=remaining)).isoformat(),
            # v1.7: the exam's active-time budget is the paper duration minus
            # the practice time already actively spent
            "duration_budget_seconds": remaining,
            "elapsed_seconds": 0,
            "last_seen_at": now.isoformat(),
            "max_score": total_score,
            "passing_score": round(total_score * _PAPER_PASS_RATIO),
            "duration_minutes": duration,
            "language_mode": cfg.get("language_mode", "en"),
            "switched_from": str(ps.id),
        },
    )
    session.add(es)
    session.flush()
    for a in session.execute(
        select(PracticeAnswer).where(PracticeAnswer.session_id == ps.id)
    ).scalars().all():
        session.add(ExamAnswer(
            session_id=es.id, user_id=user_id, question_id=a.question_id,
            question_snapshot=a.question_snapshot,
            options_snapshot=a.options_snapshot,
            user_answer=a.user_answer, is_correct=a.is_correct,
            time_spent_ms=a.time_spent_ms,
        ))
    ps.status = PracticeSessionStatus.abandoned
    ps.ended_at = now
    session.flush()
    _switch_audit(session, org_id=org_id, user_id=user_id,
                  entity_type="exam_session", entity_id=es.id,
                  switched_from=ps.id, mode=mode)
    return {"session_id": str(es.id), "kind": "exam", "paper_id": paper_id}


def _switch_from_exam(
    session: Session, *, es: ExamSession, user_id, org_id, mode: str
) -> dict:
    cfg = es.config or {}
    paper_id = cfg.get("paper_id")
    if mode == "exam":
        return {"session_id": str(es.id), "kind": "exam", "paper_id": paper_id}
    if es.status != ExamSessionStatus.in_progress:
        raise ConflictError("session is not in progress")
    if not paper_id:
        raise ValidationError("session is not attached to a paper")
    now = datetime.now(timezone.utc)
    # v1.7: seed the practice clock with the exam's ACTIVE elapsed time
    # (budget − remaining); wall clock only for legacy exams without a budget
    budget = cfg.get("duration_budget_seconds")
    if budget is not None:
        elapsed = min(int(budget), practice_elapsed_seconds(es))
    else:
        started = es.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        elapsed = max(0, int((now - started).total_seconds()))
    qids = [str(q) for q in (cfg.get("question_ids") or [])]

    from app.services.wrong_book import record_outcome

    ps = PracticeSession(
        user_id=user_id,
        organization_id=org_id,
        status=PracticeSessionStatus.in_progress,
        total_questions=len(qids),
        correct_count=0,
        config={
            "paper_id": paper_id,
            "paper_name": cfg.get("paper_name"),
            "subset": "paper",
            "order_mode": "sequential",
            "count": len(qids),
            "language_mode": cfg.get("language_mode", "en"),
            "shuffle_options": False,
            "question_ids": qids,
            "elapsed_seconds": elapsed,
            "last_seen_at": now.isoformat(),
            "switched_from": str(es.id),
        },
    )
    session.add(ps)
    session.flush()
    correct = 0
    for a in session.execute(
        select(ExamAnswer).where(ExamAnswer.session_id == es.id)
    ).scalars().all():
        session.add(PracticeAnswer(
            session_id=ps.id, user_id=user_id, question_id=a.question_id,
            question_snapshot=a.question_snapshot,
            options_snapshot=a.options_snapshot,
            user_answer=a.user_answer, is_correct=a.is_correct,
            time_spent_ms=a.time_spent_ms,
        ))
        if a.is_correct:
            correct += 1
        # judged copies feed the wrong book exactly like a practice submit
        # (the abandoned exam never applies its own outcomes)
        if a.is_correct is not None:
            record_outcome(
                session, user_id=user_id, question_id=a.question_id,
                is_correct=a.is_correct,
            )
    ps.correct_count = correct
    es.status = ExamSessionStatus.aborted
    es.ended_at = now
    session.flush()
    _switch_audit(session, org_id=org_id, user_id=user_id,
                  entity_type="practice_session", entity_id=ps.id,
                  switched_from=es.id, mode=mode)
    return {"session_id": str(ps.id), "kind": "practice", "paper_id": paper_id}
