"""Fixed + CAT exam service (sub-project F).

Owns fixed-count exam session creation with domain-weighted auto-assembly
from the current ExamBlueprint, timed feedback-free delivery with lazy
auto-submit, revisable answer submission (judged from snapshot), finish +
report, unified post-exam review, and history/trend — plus the rule-driven
CAT variant reusing ``ExamSession`` (``session_kind=cat``).

Language-mode candidate filtering + bilingual delivery/report/review reuse
the shared helpers in ``app.services.i18n`` (so practice and exam share one
implementation without an import cycle). A session's ``language_mode`` is
resolved at creation (payload > user default > "en"), stamped into
``config["language_mode"]``, and used to:
  * filter candidate questions by ``Question.available_languages`` (fixed
    assembly + CAT pool), and
  * freeze the delivered mode into each answer snapshot (``language_mode``
    field) so historical records never change (NFR-DATA-01).
Delivery / report / review always render Localized ``{en, zh}`` payloads so a
single response serves any mode.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.queries import not_deleted
from app.models.enums import (
    AuditAction,
    ExamSessionKind,
    ExamSessionStatus,
    QuestionStatus,
)
from app.models.exam import ExamAnswer, ExamSession
from app.models.question import Question, QuestionMapping, QuestionOption
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
from app.services import cat_engine
from app.services.audit import log_audit
from app.services.i18n import (
    delivery_options,
    language_filter,
    localized_stem,
    resolve_mode,
    translations_for,
)
from app.services.snapshot import localized_from_snapshot, snapshot_question


class ValidationError(ValueError):
    pass


class NotFound(LookupError):
    pass


class ConflictError(ValueError):
    pass


def _current_cat_params_or_default(session) -> dict:
    """NFR-DATA-01: snapshot the current CatParamsVersion into each new CAT
    session's config so later edits to the version never change existing
    sessions. Queries the model directly (rather than the admin service) to
    avoid importing ``app.services.admin`` (which is rewritten in T9 and not a
    dependency of the exam service at runtime). Falls back to
    cat_engine.DEFAULT_PARAMS when no version is current (the default test
    state)."""
    from app.models.admin import CatParamsVersion
    v = session.execute(
        select(CatParamsVersion).where(CatParamsVersion.is_current.is_(True))
    ).scalar_one_or_none()
    if v is not None:
        return dict(v.params)
    return dict(cat_engine.DEFAULT_PARAMS)


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
    session: Session, *, org_id, domain_id, mode: str
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
                        language_filter(mode),
                    )
                ),
            )
            .order_by(func.random())
        ).all()
    ]


def _assemble(
    session: Session, *, org_id, blueprint: ExamBlueprint, count: int, mode: str
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
        d.id: _domain_question_ids(session, org_id=org_id, domain_id=d.id, mode=mode)
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
    mode = resolve_mode(session, actor_id, getattr(body, "language_mode", None))
    if getattr(body, "kind", "fixed") == "cat":
        return create_cat_session(
            session, org_id=org_id, actor_id=actor_id, bp=bp, mode=mode
        )
    count = body.count if body.count else bp.max_items
    if count < bp.min_items:
        count = bp.min_items
    if count > bp.max_items:
        count = bp.max_items
    question_ids = _assemble(
        session, org_id=org_id, blueprint=bp, count=count, mode=mode
    )
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
        "language_mode": mode,
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


def _cat_candidate_pool(
    session: Session, *, org_id, blueprint: ExamBlueprint, mode: str
) -> list[dict]:
    """All published, tenant-scoped, language-eligible questions mapped to a
    domain of this blueprint, as engine-consumable candidate dicts. Deduped by
    question id (a question mapped to multiple domains counts once, first
    mapping wins). Language filtering happens here, at pool construction, so
    the candidate dicts need no new field — the engine sees only eligible
    items."""
    rows = session.execute(
        select(
            Question.id,
            Question.difficulty,
            QuestionMapping.domain_id,
            QuestionMapping.knowledge_point_id,
            Question.source,
        )
        .join(QuestionMapping, QuestionMapping.question_id == Question.id)
        .where(
            Question.organization_id == org_id,
            Question.status == QuestionStatus.published,
            not_deleted(Question),
            language_filter(mode),
            QuestionMapping.domain_id.in_(
                select(ExamDomain.id).where(ExamDomain.blueprint_id == blueprint.id)
            ),
        )
        .order_by(Question.id)
    ).all()
    out: list[dict] = []
    seen_ids: set[uuid.UUID] = set()
    for r in rows:
        if r.id in seen_ids:
            continue
        seen_ids.add(r.id)
        out.append({
            "id": str(r.id),
            "difficulty": r.difficulty,
            "domain_id": str(r.domain_id) if r.domain_id else None,
            "knowledge_point_id": str(r.knowledge_point_id) if r.knowledge_point_id else None,
            "source": r.source,
        })
    return out


def create_cat_session(
    session: Session, *, org_id, actor_id, bp: ExamBlueprint, mode: str
) -> ExamSession:
    domains = list(
        session.execute(
            select(ExamDomain)
            .where(ExamDomain.blueprint_id == bp.id)
            .order_by(ExamDomain.number)
        ).scalars().all()
    )
    if not domains:
        raise ValidationError("current blueprint has no domains configured")
    targets = _allocate(bp.max_items, [d.weight_pct for d in domains])
    domain_targets = {str(d.id): t for d, t in zip(domains, targets)}
    candidates = _cat_candidate_pool(
        session, org_id=org_id, blueprint=bp, mode=mode
    )
    if not candidates:
        raise ValidationError("not enough published questions for CAT")
    rng = random.Random()
    first_id = cat_engine.select_first_item(candidates, rng)
    if first_id is None:
        raise ValidationError("not enough published questions for CAT")
    started = datetime.now(timezone.utc)
    deadline = started + timedelta(minutes=bp.duration_minutes)
    config = {
        "kind": "cat",
        "question_ids": [],
        "next_question_id": first_id,
        "position": 0,
        "ability": cat_engine.initial_ability(),
        "se": cat_engine.DEFAULT_PARAMS["base_se"],
        "answered": 0,
        "correct": 0,
        "domain_targets": domain_targets,
        "domain_answered": {},
        "seen": [],
        "last_knowledge_point": None,
        "last_source": None,
        "deadline_at": deadline.isoformat(),
        "max_score": bp.max_score,
        "passing_score": bp.passing_score,
        "duration_minutes": bp.duration_minutes,
        "min_items": bp.min_items,
        "max_items": bp.max_items,
        "cat_params": _current_cat_params_or_default(session),
        "disclaimer": cat_engine.DISCLAIMER,
        "language_mode": mode,
    }
    es = ExamSession(
        user_id=actor_id,
        organization_id=org_id,
        blueprint_id=bp.id,
        session_kind=ExamSessionKind.cat,
        status=ExamSessionStatus.in_progress,
        total_questions=0,
        correct_count=0,
        config=config,
    )
    session.add(es)
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=actor_id, organization_id=org_id,
        entity_type="exam_session", entity_id=str(es.id),
        details={"kind": "cat", "max_items": bp.max_items},
    )
    return es


def get_next_question(session: Session, *, session_id, user_id) -> dict:
    es = _load_session(session, session_id, user_id)
    if _auto_submit_if_expired(session, es) or es.status != ExamSessionStatus.in_progress:
        raise ConflictError("exam session is not in progress")
    qid_str = es.config.get("next_question_id")
    if not qid_str:
        raise ConflictError("exam session has no next question")
    question = session.get(Question, uuid.UUID(qid_str))
    if question is None or question.deleted_at is not None:
        raise NotFound("question no longer available")
    options = _options_for(session, question.id)
    translations = translations_for(session, question.id)
    started = es.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    elapsed_ms = int(
        (datetime.now(timezone.utc) - started).total_seconds() * 1000
    )
    return {
        "session_id": str(es.id),
        "position": es.config.get("position", 0),
        "total": es.config.get("max_items", 0),
        "question_id": str(question.id),
        "question_type": question.question_type.value,
        "available_languages": list(question.available_languages or []),
        "language_mode": es.config.get("language_mode", "en"),
        "stem": localized_stem(translations),
        "options": delivery_options(options, translations),
        "elapsed_ms": elapsed_ms,
        "time_remaining_ms": _time_remaining_ms(es),
        "previous_answer": None,
    }


def _load_session(session: Session, session_id, user_id, *, for_update: bool = False) -> ExamSession:
    # `for_update` takes a row-level lock so concurrent answer submits for the
    # same exam session serialize (audit P1 #15).
    es = session.get(ExamSession, session_id, with_for_update=for_update)
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
    translations = translations_for(session, question.id)
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
        "question_type": question.question_type.value,
        "available_languages": list(question.available_languages or []),
        "language_mode": es.config.get("language_mode", "en"),
        "stem": localized_stem(translations),
        "options": delivery_options(options, translations),
        "elapsed_ms": elapsed_ms,
        "time_remaining_ms": _time_remaining_ms(es),
        "previous_answer": (
            {"selected": prev.user_answer.get("selected")} if prev else None
        ),
    }


def submit_answer(session: Session, *, session_id, user_id, payload) -> ExamAnswerAck:
    body = payload if isinstance(payload, ExamAnswerIn) else ExamAnswerIn(**payload)
    es = _load_session(session, session_id, user_id, for_update=True)
    if es.session_kind == ExamSessionKind.cat:
        return _submit_cat_answer(session, es=es, user_id=user_id, payload=body)
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
    translations = translations_for(session, question_id)
    snap = snapshot_question(
        question, translations, options,
        language_mode=es.config.get("language_mode"),
    )
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


def _submit_cat_answer(
    session: Session, *, es: ExamSession, user_id, payload
) -> ExamAnswerAck:
    body = payload if isinstance(payload, ExamAnswerIn) else ExamAnswerIn(**payload)
    if _auto_submit_if_expired(session, es) or es.status != ExamSessionStatus.in_progress:
        raise ConflictError("exam session is not in progress")
    cfg = es.config
    if body.position != cfg.get("position", 0):
        raise ValidationError("position does not match current CAT position")
    qid_str = cfg.get("next_question_id")
    if not qid_str:
        raise ConflictError("exam session has no next question")
    question_id = uuid.UUID(qid_str)
    question = session.get(Question, question_id)
    if question is None or question.deleted_at is not None:
        raise NotFound("question no longer available")
    options = _options_for(session, question_id)
    translations = translations_for(session, question_id)
    snap = snapshot_question(
        question, translations, options,
        language_mode=cfg.get("language_mode"),
    )
    is_correct = _judge(snap, body.selected)
    now = datetime.now(timezone.utc)
    started = body.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    time_spent_ms = max(0, int((now - started).total_seconds() * 1000))

    params = cfg.get("cat_params", dict(cat_engine.DEFAULT_PARAMS))
    prev_answered = cfg.get("answered", 0)
    answered = prev_answered + 1
    new_ability = cat_engine.update_ability(
        cfg.get("ability", cat_engine.initial_ability()),
        question.difficulty, is_correct, prev_answered, params,
    )
    new_se = cat_engine.sem(answered, params)

    # Domain + knowledge point of the answered item (for coverage + anti-cluster).
    mapping = session.execute(
        select(QuestionMapping).where(QuestionMapping.question_id == question_id)
    ).scalars().first()
    domain_id = str(mapping.domain_id) if mapping and mapping.domain_id else None
    kp = str(mapping.knowledge_point_id) if mapping and mapping.knowledge_point_id else None

    ans = ExamAnswer(session_id=es.id, user_id=user_id, question_id=question_id)
    session.add(ans)
    ans.question_snapshot = snap
    ans.options_snapshot = snap["options"]
    ans.user_answer = {"selected": body.selected}
    ans.is_correct = is_correct
    ans.time_spent_ms = time_spent_ms
    ans.ability_estimate_after = new_ability
    ans.se_after = new_se
    ans.answered_at = now

    # Update CAT runtime state in config.
    cfg["question_ids"] = cfg.get("question_ids", []) + [str(question_id)]
    cfg["seen"] = cfg.get("seen", []) + [str(question_id)]
    cfg["answered"] = answered
    cfg["correct"] = cfg.get("correct", 0) + (1 if is_correct else 0)
    cfg["ability"] = new_ability
    cfg["se"] = new_se
    if domain_id:
        cfg["domain_answered"][domain_id] = cfg["domain_answered"].get(domain_id, 0) + 1
    cfg["last_knowledge_point"] = kp
    cfg["last_source"] = question.source

    min_items = cfg.get("min_items", cat_engine.MIN_ITEMS_DEFAULT)
    max_items = cfg.get("max_items", cat_engine.MAX_ITEMS_DEFAULT)
    pa = cat_engine.passing_ability(
        cfg.get("passing_score", 700), cfg.get("max_score", 1000)
    )
    decision = cat_engine.decide_termination(
        answered, new_ability, new_se, min_items, max_items, False, pa, params
    )

    finished = False
    if decision.must_stop:
        finished = True
        es.status = ExamSessionStatus.completed
        es.ended_at = now
        es.total_questions = answered
        es.correct_count = cfg["correct"]
        cfg["next_question_id"] = None
    else:
        bp = session.get(ExamBlueprint, es.blueprint_id)
        candidates = _cat_candidate_pool(
            session, org_id=es.organization_id, blueprint=bp,
            mode=cfg.get("language_mode", "en"),
        )
        rng = random.Random()
        next_id = cat_engine.select_next_item(
            candidates, new_ability, cfg.get("domain_targets", {}),
            cfg.get("domain_answered", {}), cfg.get("seen", []),
            kp, question.source, rng,
        )
        if next_id is None:
            # Pool exhausted: terminate.
            finished = True
            es.status = ExamSessionStatus.completed
            es.ended_at = now
            es.total_questions = answered
            es.correct_count = cfg["correct"]
            cfg["next_question_id"] = None
        else:
            cfg["next_question_id"] = next_id
            cfg["position"] = cfg.get("position", 0) + 1

    flag_modified(es, "config")
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=user_id,
        organization_id=es.organization_id, entity_type="exam_answer",
        entity_id=str(ans.id),
        details={"is_correct": is_correct, "ability": new_ability, "finished": finished},
    )
    return ExamAnswerAck(
        position=body.position, saved=True,
        time_remaining_ms=_time_remaining_ms(es), finished=finished,
    )


def _domain_and_wrong(session: Session, es: ExamSession, qids, answers):
    """Shared per-domain grouping + wrong-question list (snapshot-sourced).

    Wrong-question stems render Localized {en,zh} from the frozen snapshot via
    ``localized_from_snapshot`` (later edits to live translations never change
    historical review)."""
    domain_rows = list(
        session.execute(
            select(ExamDomain).where(ExamDomain.blueprint_id == es.blueprint_id)
        ).scalars().all()
    )
    domain_by_id = {d.id: d for d in domain_rows}
    qid_to_domain: dict[uuid.UUID, uuid.UUID | None] = {}
    if qids:
        mapping_rows = session.execute(
            select(QuestionMapping.question_id, QuestionMapping.domain_id).where(
                QuestionMapping.question_id.in_(qids)
            )
        ).all()
        for qid, did in mapping_rows:
            qid_to_domain.setdefault(qid, did)
    answer_by_qid = {a.question_id: a for a in answers}
    per_domain: dict[uuid.UUID | None, dict] = {}
    for qid in qids:
        did = qid_to_domain.get(qid)
        bucket = per_domain.setdefault(did, {"answered": 0, "correct": 0})
        a = answer_by_qid.get(qid)
        if a is not None:
            bucket["answered"] += 1
            if a.is_correct:
                bucket["correct"] += 1
    domains = [
        DomainPerformance(
            domain_id=did,
            domain_name=domain_by_id[did].name if did in domain_by_id else None,
            weight_pct=domain_by_id[did].weight_pct if did in domain_by_id else None,
            answered=b["answered"],
            correct=b["correct"],
            accuracy=b["correct"] / b["answered"] if b["answered"] else 0.0,
        )
        for did, b in per_domain.items()
    ]
    wrong = []
    for a in answers:
        if a.is_correct:
            continue
        snap = a.question_snapshot or {}
        view = localized_from_snapshot(snap, snap.get("language_mode") or "en")
        correct_indexes = [
            o["order_index"] for o in (a.options_snapshot or []) if o.get("is_correct")
        ]
        selected = (a.user_answer or {}).get("selected", [])
        wrong.append(WrongQuestion(
            question_id=a.question_id,
            stem=view["stem"],
            selected_indexes=list(selected),
            correct_indexes=correct_indexes,
        ))
    return domains, wrong


def _build_report(session: Session, es: ExamSession) -> ExamReportOut:
    if es.session_kind == ExamSessionKind.cat:
        return _build_cat_report(session, es)
    cfg = es.config or {}
    max_score = cfg.get("max_score", 1000)
    passing_score = cfg.get("passing_score", 700)
    qids = [uuid.UUID(q) for q in cfg.get("question_ids", [])]
    total = len(qids) or es.total_questions

    answers = list(
        session.execute(
            select(ExamAnswer).where(ExamAnswer.session_id == es.id)
        ).scalars().all()
    )
    answered = len(answers)
    correct = sum(1 for a in answers if a.is_correct)

    scaled_score = round(correct / total * max_score) if total else 0
    passed = scaled_score >= passing_score
    accuracy = correct / answered if answered else 0.0
    total_time = sum(a.time_spent_ms or 0 for a in answers)
    avg_time = total_time / answered if answered else 0.0

    domains, wrong = _domain_and_wrong(session, es, qids, answers)

    return ExamReportOut(
        session_id=es.id,
        status=es.status.value if hasattr(es.status, "value") else es.status,
        total_questions=total,
        answered_count=answered,
        correct_count=correct,
        scaled_score=scaled_score,
        max_score=max_score,
        passing_score=passing_score,
        passed=passed,
        accuracy=accuracy,
        total_time_ms=total_time,
        avg_time_ms=avg_time,
        domains=domains,
        wrong_questions=wrong,
    )


def _build_cat_report(session: Session, es: ExamSession) -> ExamReportOut:
    cfg = es.config or {}
    max_score = cfg.get("max_score", 1000)
    passing_score = cfg.get("passing_score", 700)
    ability = cfg.get("ability", cat_engine.initial_ability())
    se_value = cfg.get("se", cat_engine.DEFAULT_PARAMS["base_se"])
    qids = [uuid.UUID(q) for q in cfg.get("question_ids", [])]
    total = len(qids) or es.total_questions

    answers = list(
        session.execute(
            select(ExamAnswer).where(ExamAnswer.session_id == es.id)
        ).scalars().all()
    )
    answered = len(answers)
    correct = sum(1 for a in answers if a.is_correct)

    scaled_score = cat_engine.scaled_score(ability, max_score)
    passed = scaled_score >= passing_score
    accuracy = correct / answered if answered else 0.0
    total_time = sum(a.time_spent_ms or 0 for a in answers)
    avg_time = total_time / answered if answered else 0.0

    domains, wrong = _domain_and_wrong(session, es, qids, answers)
    ci_lo, ci_hi = cat_engine.confidence_interval(ability, se_value)

    return ExamReportOut(
        session_id=es.id,
        status=es.status.value if hasattr(es.status, "value") else es.status,
        total_questions=total,
        answered_count=answered,
        correct_count=correct,
        scaled_score=scaled_score,
        max_score=max_score,
        passing_score=passing_score,
        passed=passed,
        accuracy=accuracy,
        total_time_ms=total_time,
        avg_time_ms=avg_time,
        domains=domains,
        wrong_questions=wrong,
        ability_estimate=ability,
        ability_ci_lower=ci_lo,
        ability_ci_upper=ci_hi,
        sem=se_value,
        readiness_level=cat_engine.readiness_level(ability),
        disclaimer=cfg.get("disclaimer"),
    )


def finish_session(session: Session, *, session_id, user_id) -> ExamReportOut:
    es = _load_session(session, session_id, user_id)
    _auto_submit_if_expired(session, es)
    if es.status == ExamSessionStatus.in_progress:
        es.status = ExamSessionStatus.completed
        es.ended_at = datetime.now(timezone.utc)
        if es.session_kind == ExamSessionKind.cat:
            cfg = es.config
            es.total_questions = cfg.get("answered", 0)
            cfg["next_question_id"] = None
            flag_modified(es, "config")
        session.flush()
    # Recompute correct_count from stored answers.
    answers = list(
        session.execute(
            select(ExamAnswer).where(ExamAnswer.session_id == es.id)
        ).scalars().all()
    )
    es.correct_count = sum(1 for a in answers if a.is_correct)
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=user_id,
        organization_id=es.organization_id, entity_type="exam_session",
        entity_id=str(es.id),
        details={"status": es.status.value, "correct_count": es.correct_count},
    )
    return _build_report(session, es)


def get_report(session: Session, *, session_id, user_id) -> ExamReportOut:
    es = _load_session(session, session_id, user_id)
    if es.status == ExamSessionStatus.in_progress:
        raise ConflictError("exam session is not finished")
    return _build_report(session, es)


def _opt_localized(order_index: int, translations, field: str) -> dict:
    """Render a single per-option field as a Localized {en,zh} dict by reading
    each translation's ``options`` JSONB by ``order_index``. Used for the
    never-answered review branch where content/explanation come from live
    translations rather than a frozen snapshot."""
    out = {"en": None, "zh": None}
    for t in translations:
        to = next(
            (o for o in (t.options or []) if o.get("order_index") == order_index),
            None,
        )
        if to:
            out[t.language] = to.get(field)
    return out


def get_review(session: Session, *, session_id, user_id) -> list:
    es = _load_session(session, session_id, user_id)
    if es.status == ExamSessionStatus.in_progress:
        raise ConflictError("exam session is not finished")
    qids = es.config.get("question_ids", [])
    items: list = []
    for position, qid_str in enumerate(qids):
        question_id = uuid.UUID(qid_str)
        question = session.get(Question, question_id)
        ans = session.execute(
            select(ExamAnswer).where(
                ExamAnswer.session_id == es.id,
                ExamAnswer.question_id == question_id,
            )
        ).scalars().first()
        # Answered items render from the frozen snapshot (NFR-DATA-01): later
        # edits to live options/translations never change the review.
        if ans is not None and ans.options_snapshot:
            snap = ans.question_snapshot or {}
            view = localized_from_snapshot(snap, snap.get("language_mode") or "en")
            opts = [
                {
                    "order_index": o["order_index"],
                    "content": o["content"],
                    "is_correct": o["is_correct"],
                    "explanation": o["explanation"],
                }
                for o in view["options"]
            ]
            stem = view["stem"]
            qtype = snap.get("question_type", "")
            rationale = view["correct_rationale"]
            key_point = view["key_point_summary"]
            avail = view["available_languages"]
        else:
            # Never answered (lazy auto-submit / manual finish mid-exam):
            # build Localized view from live translations.
            translations = translations_for(session, question_id) if question else []
            live_opts = _options_for(session, question_id) if question else []
            opts = [
                {
                    "order_index": o.order_index,
                    "content": _opt_localized(o.order_index, translations, "content"),
                    "is_correct": o.is_correct,
                    "explanation": _opt_localized(o.order_index, translations, "explanation"),
                }
                for o in live_opts
            ]
            stem = localized_stem(translations)
            qtype = question.question_type.value if question else ""
            rationale = {
                "en": next(
                    (t.correct_answer_rationale for t in translations if t.language == "en"),
                    None,
                ),
                "zh": next(
                    (t.correct_answer_rationale for t in translations if t.language == "zh"),
                    None,
                ),
            }
            key_point = {
                "en": next(
                    (t.key_point_summary for t in translations if t.language == "en"),
                    None,
                ),
                "zh": next(
                    (t.key_point_summary for t in translations if t.language == "zh"),
                    None,
                ),
            }
            avail = list(question.available_languages or []) if question else []
        items.append(
            ReviewItemOut(
                position=position,
                question_id=question_id,
                question_type=qtype,
                available_languages=avail,
                stem=stem,
                options=opts,
                correct_rationale=rationale,
                key_point_summary=key_point,
                your_answer=(
                    {
                        "selected": ans.user_answer.get("selected"),
                        "is_correct": ans.is_correct,
                    }
                    if ans
                    else None
                ),
                time_spent_ms=ans.time_spent_ms if ans else None,
            )
        )
    return items


def _scaled(es: ExamSession) -> tuple[int, bool, float, int, int]:
    """Return (scaled_score, passed, accuracy, total, correct) for a history row.

    For CAT sessions the stored total_questions/correct_count columns are only
    reconciled on normal termination (decide_termination in _submit_cat_answer
    or the in_progress branch of finish_session); _auto_submit_if_expired only
    flips status + ended_at, so a time-up (auto_submitted) CAT row still reads
    0/0. Prefer the live CAT runtime state in config ("answered"/"correct")
    over the stale columns. For fixed-exam sessions the columns are
    authoritative and are read directly (behavior unchanged).
    """
    max_score = es.config.get("max_score", 0)
    passing_score = es.config.get("passing_score", 0)
    if es.session_kind == ExamSessionKind.cat:
        total = es.config.get("answered", 0) or es.total_questions or 0
        correct = es.config.get("correct", 0)
        ability = es.config.get("ability", cat_engine.initial_ability())
        scaled = cat_engine.scaled_score(ability, max_score)
        accuracy = (correct / total) if total else 0.0
        return scaled, scaled >= passing_score, accuracy, total, correct
    total = es.total_questions or 0
    correct = es.correct_count or 0
    scaled = round((correct / total) * max_score) if total else 0
    passed = scaled >= passing_score
    accuracy = (correct / total) if total else 0.0
    return scaled, passed, accuracy, total, correct


def list_history(session: Session, *, user_id, limit: int = 50, offset: int = 0) -> list:
    rows = list(
        session.execute(
            select(ExamSession).where(
                ExamSession.user_id == user_id,
                ExamSession.status.in_([
                    ExamSessionStatus.completed,
                    ExamSessionStatus.auto_submitted,
                ]),
            ).order_by(ExamSession.started_at.asc())
            .limit(limit).offset(offset)
        ).scalars().all()
    )
    out: list = []
    for es in rows:
        scaled, passed, accuracy, total, correct = _scaled(es)
        out.append(
            ExamHistoryItemOut(
                id=es.id,
                started_at=es.started_at,
                ended_at=es.ended_at,
                status=es.status.value,
                total_questions=total,
                correct_count=correct,
                scaled_score=scaled,
                max_score=es.config.get("max_score", 0),
                passed=passed,
                accuracy=accuracy,
            )
        )
    return out
