"""Service-layer tests for fixed exam API (sub-project F)."""

import pytest

from app.models.auth import Organization, User
from app.models.enums import (
    OrgKind,
    QuestionStatus,
    QuestionType,
    TextFormat,
)
from app.models.exam import ExamSession
from app.models.question import Question, QuestionOption
from app.services import exam as svc


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


def _question(db_session, org, actor, *, stem="q",
              qtype=QuestionType.single_choice, options=None):
    q = Question(
        organization_id=org.id,
        question_type=qtype,
        stem=stem,
        stem_format=TextFormat.markdown,
        status=QuestionStatus.published,
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


def test_exam_session_has_config_column(db_session):
    """ExamSession must expose a config JSONB column (default '{}')."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    from app.models.enums import ExamSessionKind
    from app.models.taxonomy import ExamBlueprint

    bp = ExamBlueprint(
        version_label="v1", effective_date="2026-04-15",
        min_items=1, max_items=10, duration_minutes=30,
        passing_score=700, max_score=1000, is_current=True,
    )
    db_session.add(bp)
    db_session.flush()
    es = ExamSession(
        user_id=actor.id, organization_id=org.id, blueprint_id=bp.id,
        session_kind=ExamSessionKind.fixed, total_questions=0,
    )
    db_session.add(es)
    db_session.flush()
    assert es.config is not None


def _blueprint(db_session, *, current=True, min_items=1, max_items=10,
               duration_minutes=30, passing_score=700, max_score=1000,
               version="v1"):
    from app.models.taxonomy import ExamBlueprint, ExamDomain

    bp = ExamBlueprint(
        version_label=version, effective_date="2026-04-15",
        min_items=min_items, max_items=max_items,
        duration_minutes=duration_minutes, passing_score=passing_score,
        max_score=max_score, is_current=current,
    )
    db_session.add(bp)
    db_session.flush()
    return bp


def _domain(db_session, bp, *, number, name, weight_pct):
    from app.models.taxonomy import ExamDomain

    d = ExamDomain(
        blueprint_id=bp.id, number=number, name=name, weight_pct=weight_pct,
    )
    db_session.add(d)
    db_session.flush()
    return d


def _map(db_session, question, domain=None):
    from app.models.question import QuestionMapping

    m = QuestionMapping(question_id=question.id)
    if domain is not None:
        m.domain_id = domain.id
    db_session.add(m)
    db_session.flush()
    return m


def test_assemble_weights_sum_to_count(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=4, max_items=10)
    d1 = _domain(db_session, bp, number=1, name="D1", weight_pct=50)
    d2 = _domain(db_session, bp, number=2, name="D2", weight_pct=50)
    for i in range(5):
        q = _question(db_session, org, actor, stem=f"a{i}")
        _map(db_session, q, d1)
    for i in range(5):
        q = _question(db_session, org, actor, stem=f"b{i}")
        _map(db_session, q, d2)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload={"count": 4},
    )
    assert es.total_questions == 4
    assert len(es.config["question_ids"]) == 4
    assert es.config["count"] == 4
    assert es.config["max_score"] == 1000
    assert es.config["passing_score"] == 700
    assert es.config["duration_minutes"] == 30
    assert "deadline_at" in es.config


def test_assemble_redistributes_short_domain(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=4, max_items=10)
    d1 = _domain(db_session, bp, number=1, name="D1", weight_pct=50)
    d2 = _domain(db_session, bp, number=2, name="D2", weight_pct=50)
    # D1 has only 1 question but targets 2 -> shortfall filled from D2.
    q = _question(db_session, org, actor, stem="only1")
    _map(db_session, q, d1)
    for i in range(5):
        q = _question(db_session, org, actor, stem=f"d2-{i}")
        _map(db_session, q, d2)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload={"count": 4},
    )
    assert es.total_questions == 4  # 1 from D1 + 3 from D2


def test_assemble_shortage_rejected(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=1, max_items=10)
    d1 = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    _question(db_session, org, actor, stem="solo")
    # only 1 published question available but count=4
    with pytest.raises(svc.ValidationError):
        svc.create_session(
            db_session, org_id=org.id, actor_id=actor.id,
            payload={"count": 4},
        )


def test_no_current_blueprint_rejected(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _blueprint(db_session, current=False)
    _question(db_session, org, actor)
    with pytest.raises(svc.ValidationError):
        svc.create_session(
            db_session, org_id=org.id, actor_id=actor.id,
            payload={"count": 1},
        )


def test_create_count_clamped_to_bounds(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=5, max_items=8)
    d1 = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    for i in range(10):
        _map(db_session, _question(db_session, org, actor, stem=f"q{i}"), d1)
    # count below min -> clamped up to min_items=5
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"count": 2},
    )
    assert es.total_questions == 5
    # count above max -> clamped down to max_items=8
    es2 = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"count": 99},
    )
    assert es2.total_questions == 8


def test_create_default_count_is_max_items(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=1, max_items=3)
    d1 = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    for i in range(5):
        _map(db_session, _question(db_session, org, actor, stem=f"q{i}"), d1)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={},
    )
    assert es.total_questions == 3  # default = max_items


def _start(db_session, org, actor, *, count=1, bp=None):
    if bp is None:
        bp = _blueprint(db_session, min_items=1, max_items=10)
        d = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
        q = _question(db_session, org, actor, stem="q1")
        _map(db_session, q, d)
    return svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"count": count},
    )


def test_delivery_strips_correctness_and_has_timing(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    s = _start(db_session, org, actor, count=1)
    out = svc.get_question_at(
        db_session, session_id=s.id, position=0, user_id=actor.id
    )
    assert out["position"] == 0
    assert out["total"] == 1
    assert out["stem"] == "q1"
    for opt in out["options"]:
        assert "is_correct" not in opt
    assert out["time_remaining_ms"] > 0
    assert out["elapsed_ms"] >= 0
    assert out["previous_answer"] is None


def test_submit_answer_returns_ack_no_judgment(db_session):
    from datetime import datetime, timezone

    org = _org(db_session)
    actor = _actor(db_session, org)
    s = _start(db_session, org, actor, count=1)
    ack = svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    assert ack.saved is True
    assert ack.position == 0
    assert ack.time_remaining_ms > 0


def test_answer_is_revisable_single_row(db_session):
    from datetime import datetime, timezone

    from app.models.exam import ExamAnswer

    org = _org(db_session)
    actor = _actor(db_session, org)
    s = _start(db_session, org, actor, count=1)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [1],
                 "started_at": datetime.now(timezone.utc)},
    )
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    rows = db_session.query(ExamAnswer).filter_by(session_id=s.id).all()
    assert len(rows) == 1
    assert rows[0].user_answer == {"selected": [0]}
    assert rows[0].is_correct is True  # judged from snapshot at revise time


def test_answer_persists_snapshot(db_session):
    from datetime import datetime, timezone

    from app.models.exam import ExamAnswer

    org = _org(db_session)
    actor = _actor(db_session, org)
    s = _start(db_session, org, actor, count=1)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    ans = db_session.query(ExamAnswer).filter_by(session_id=s.id).one()
    assert ans.options_snapshot[0]["is_correct"] is True
    assert ans.is_correct is True


def test_delivery_returns_previous_answer(db_session):
    from datetime import datetime, timezone

    org = _org(db_session)
    actor = _actor(db_session, org)
    s = _start(db_session, org, actor, count=1)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [1],
                 "started_at": datetime.now(timezone.utc)},
    )
    out = svc.get_question_at(
        db_session, session_id=s.id, position=0, user_id=actor.id
    )
    assert out["previous_answer"] == {"selected": [1]}


def test_lazy_auto_submit_after_deadline(db_session):
    from datetime import datetime, timezone

    from app.models.enums import ExamSessionStatus

    org = _org(db_session)
    actor = _actor(db_session, org)
    s = _start(db_session, org, actor, count=1)
    # Force the deadline into the past.
    s.config["deadline_at"] = (datetime.now(timezone.utc)).isoformat()
    db_session.flush()
    with pytest.raises(svc.ConflictError):
        svc.get_question_at(
            db_session, session_id=s.id, position=0, user_id=actor.id
        )
    assert db_session.get(ExamSession, s.id).status == ExamSessionStatus.auto_submitted


def test_position_out_of_range_rejected(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    s = _start(db_session, org, actor, count=1)
    with pytest.raises(svc.ValidationError):
        svc.get_question_at(
            db_session, session_id=s.id, position=5, user_id=actor.id
        )


def test_other_user_exam_not_found(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    intruder = _actor(db_session, org, email="other@example.com")
    s = _start(db_session, org, actor, count=1)
    with pytest.raises(svc.NotFound):
        svc.get_question_at(
            db_session, session_id=s.id, position=0, user_id=intruder.id
        )
