"""Service-layer tests for fixed exam API (sub-project F)."""

import uuid

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
              qtype=QuestionType.single_choice, options=None, difficulty=None):
    q = Question(
        organization_id=org.id,
        question_type=qtype,
        stem=stem,
        stem_format=TextFormat.markdown,
        status=QuestionStatus.published,
        created_by_id=actor.id,
        difficulty=difficulty,
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


def _two_question_exam(db_session, *, passing_score=700, max_score=1000):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(
        db_session, min_items=2, max_items=2, passing_score=passing_score,
        max_score=max_score,
    )
    d = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    q1 = _question(db_session, org, actor, stem="right")  # option 0 correct
    q2 = _question(db_session, org, actor, stem="wrong")  # option 0 correct
    _map(db_session, q1, d)
    _map(db_session, q2, d)
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"count": 2},
    )
    return org, actor, s, (q1, q2)


def test_finish_recomputes_correct_count_and_score(db_session):
    from datetime import datetime, timezone

    org, actor, s, (q1, q2) = _two_question_exam(db_session)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 1, "selected": [1],
                 "started_at": datetime.now(timezone.utc)},
    )
    report = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert report.total_questions == 2
    assert report.answered_count == 2
    assert report.correct_count == 1
    # 1/2 * 1000 = 500
    assert report.scaled_score == 500
    assert report.max_score == 1000
    assert report.passing_score == 700
    assert report.passed is False
    assert report.accuracy == 0.5
    assert len(report.wrong_questions) == 1
    # position 1 was answered wrong; the wrong question is whichever question
    # landed at position 1 (assembly shuffles the order).
    wrong_qid = uuid.UUID(s.config["question_ids"][1])
    assert report.wrong_questions[0].question_id == wrong_qid
    assert report.wrong_questions[0].correct_indexes == [0]
    assert report.wrong_questions[0].selected_indexes == [1]


def test_finish_per_domain_performance(db_session):
    from datetime import datetime, timezone

    org, actor, s, _ = _two_question_exam(db_session)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 1, "selected": [1],
                 "started_at": datetime.now(timezone.utc)},
    )
    report = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert len(report.domains) == 1
    assert report.domains[0].answered == 2
    assert report.domains[0].correct == 1
    assert report.domains[0].accuracy == 0.5


def test_finish_passing_line(db_session):
    from datetime import datetime, timezone

    org, actor, s, _ = _two_question_exam(db_session, passing_score=0, max_score=1000)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    report = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert report.passed is True  # 500 >= 0


def test_finish_recomputes_after_revision(db_session):
    from datetime import datetime, timezone

    org, actor, s, _ = _two_question_exam(db_session)
    # answer both wrong first
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [1],
                 "started_at": datetime.now(timezone.utc)},
    )
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 1, "selected": [1],
                 "started_at": datetime.now(timezone.utc)},
    )
    # revise position 0 to correct
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    report = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert report.correct_count == 1  # only the revised answer counts


def test_finish_idempotent(db_session):
    from datetime import datetime, timezone

    from app.models.enums import ExamSessionStatus

    org, actor, s, _ = _two_question_exam(db_session)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    a = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    b = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert a.correct_count == b.correct_count
    assert db_session.get(ExamSession, s.id).status == ExamSessionStatus.completed


def test_get_report_after_finish(db_session):
    from datetime import datetime, timezone

    org, actor, s, _ = _two_question_exam(db_session)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    report = svc.get_report(db_session, session_id=s.id, user_id=actor.id)
    assert report.correct_count == 1


def test_review_only_after_finish(db_session):
    from datetime import datetime, timezone

    org, actor, s, _ = _two_question_exam(db_session)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    with pytest.raises(svc.ConflictError):
        svc.get_review(db_session, session_id=s.id, user_id=actor.id)
    svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    review = svc.get_review(db_session, session_id=s.id, user_id=actor.id)
    assert len(review) == 2
    assert review[0].position == 0
    assert review[0].your_answer["is_correct"] is True
    # options expose is_correct (from snapshot)
    assert any(o.is_correct for o in review[0].options)


def test_review_reads_correctness_from_snapshot(db_session):
    from datetime import datetime, timezone

    from app.models.question import QuestionOption

    org, actor, s, (q1, q2) = _two_question_exam(db_session)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    # Mutate the live question so option 0 is now WRONG and option 1 is RIGHT.
    opt0 = db_session.query(QuestionOption).filter_by(
        question_id=q1.id, order_index=0).one()
    opt1 = db_session.query(QuestionOption).filter_by(
        question_id=q1.id, order_index=1).one()
    opt0.is_correct = False
    opt1.is_correct = True
    db_session.flush()
    svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    review = svc.get_review(db_session, session_id=s.id, user_id=actor.id)
    item0 = review[0]
    # snapshot still says order_index 0 was correct
    assert item0.options[0].is_correct is True
    assert item0.options[1].is_correct is False
    # the answer was judged correct against the original snapshot
    assert item0.your_answer["is_correct"] is True


def test_history_ordered_and_only_finished(db_session):
    from datetime import datetime, timezone

    org = _org(db_session)
    actor = _actor(db_session, org)
    # first exam: 1 question, finished
    bp1 = _blueprint(db_session, min_items=1, max_items=1, version="v1")
    d1 = _domain(db_session, bp1, number=1, name="D1", weight_pct=100)
    q = _question(db_session, org, actor, stem="q")
    _map(db_session, q, d1)
    s1 = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"count": 1})
    svc.submit_answer(
        db_session, session_id=s1.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)})
    svc.finish_session(db_session, session_id=s1.id, user_id=actor.id)
    # second exam: in progress (should NOT appear)
    s2 = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"count": 1})
    hist = svc.list_history(db_session, user_id=actor.id)
    assert len(hist) == 1
    assert hist[0].id == s1.id
    assert hist[0].scaled_score == 1000
    assert hist[0].passed is True


def test_history_uses_historical_scoring_basis(db_session):
    from datetime import datetime, timezone

    from app.models.taxonomy import ExamBlueprint

    org, actor, s, _ = _two_question_exam(
        db_session, passing_score=700, max_score=1000)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)})
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 1, "selected": [1],
                 "started_at": datetime.now(timezone.utc)})
    svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    # Now lower the blueprint's passing score to 0 -> would pass if recomputed.
    bp = db_session.get(ExamBlueprint, s.blueprint_id)
    bp.passing_score = 0  # if history recomputed, passed would flip to True
    db_session.flush()
    hist = svc.list_history(db_session, user_id=actor.id)
    assert hist[0].passed is False  # still judged against original 700 (config basis)
    assert hist[0].scaled_score == 500


def _cat_blueprint(db_session, *, min_items=1, max_items=5, passing_score=700,
                   max_score=1000, duration_minutes=30):
    bp = _blueprint(
        db_session, min_items=min_items, max_items=max_items,
        passing_score=passing_score, max_score=max_score,
        duration_minutes=duration_minutes, version="cat-v1",
    )
    d1 = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    return bp, d1


def _seed_cat_questions(db_session, org, actor, domain, n=5, difficulty=3):
    qs = []
    for i in range(n):
        q = _question(db_session, org, actor, stem=f"cat-q{i}", difficulty=difficulty)
        _map(db_session, q, domain)
        qs.append(q)
    return qs


def test_create_cat_session_medium_start_and_config_shape(db_session):
    from app.models.enums import ExamSessionKind, ExamSessionStatus

    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(db_session, min_items=1, max_items=5)
    _seed_cat_questions(db_session, org, actor, d1, n=5, difficulty=3)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"kind": "cat"}
    )
    assert es.session_kind == ExamSessionKind.cat
    assert es.status == ExamSessionStatus.in_progress
    cfg = es.config
    assert cfg["kind"] == "cat"
    assert cfg["ability"] == 3.0
    assert cfg["answered"] == 0
    assert cfg["position"] == 0
    assert cfg["next_question_id"]  # first item selected
    assert cfg["question_ids"] == []
    assert cfg["max_items"] == 5
    assert cfg["min_items"] == 1
    assert "deadline_at" in cfg
    assert "disclaimer" in cfg
    assert "cat_params" in cfg


def test_create_cat_first_item_is_medium_difficulty(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(db_session, min_items=1, max_items=5)
    qs = _seed_cat_questions(db_session, org, actor, d1, n=5, difficulty=3)
    # add a couple of extreme-difficulty items that must NOT be chosen first
    hard = _question(db_session, org, actor, stem="hard", difficulty=5)
    _map(db_session, hard, d1)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"kind": "cat"}
    )
    first_id = uuid.UUID(es.config["next_question_id"])
    chosen = next(q for q in qs if q.id == first_id)
    assert chosen.difficulty == 3


def test_create_cat_rejects_empty_pool(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(db_session)  # no questions seeded
    with pytest.raises(svc.ValidationError):
        svc.create_session(
            db_session, org_id=org.id, actor_id=actor.id, payload={"kind": "cat"}
        )


def test_get_next_question_strips_correctness(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(db_session, min_items=1, max_items=5)
    _seed_cat_questions(db_session, org, actor, d1, n=5)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"kind": "cat"}
    )
    out = svc.get_next_question(db_session, session_id=es.id, user_id=actor.id)
    assert out["position"] == 0
    assert out["total"] == 5
    for opt in out["options"]:
        assert "is_correct" not in opt
    assert out["previous_answer"] is None
    assert out["time_remaining_ms"] > 0


def test_get_next_question_other_user_404(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    intruder = _actor(db_session, org, email="other@example.com")
    bp, d1 = _cat_blueprint(db_session, min_items=1, max_items=5)
    _seed_cat_questions(db_session, org, actor, d1, n=5)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"kind": "cat"}
    )
    with pytest.raises(svc.NotFound):
        svc.get_next_question(db_session, session_id=es.id, user_id=intruder.id)


def _cat_start(db_session, *, passing_score=700, max_score=1000,
               min_items=1, max_items=5, n_questions=5, difficulty=3,
               early_stop=True):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(
        db_session, min_items=min_items, max_items=max_items,
        passing_score=passing_score, max_score=max_score,
    )
    _seed_cat_questions(db_session, org, actor, d1, n=n_questions, difficulty=difficulty)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"kind": "cat"}
    )
    if not early_stop:
        es.config["cat_params"]["early_stop_enabled"] = False
        flag_modified_for_test(es)
    return org, actor, es


def flag_modified_for_test(es):
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(es, "config")


def _answer(db_session, es, actor, *, selected, position):
    from datetime import datetime, timezone
    return svc.submit_answer(
        db_session, session_id=es.id, user_id=actor.id,
        payload={"position": position, "selected": selected,
                 "started_at": datetime.now(timezone.utc)},
    )


def test_cat_submit_advances_position_and_ability(db_session):
    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    # option 0 is correct on every seeded question
    ack = _answer(db_session, es, actor, selected=[0], position=0)
    assert ack.saved is True
    assert ack.finished is False
    assert es.config["answered"] == 1
    assert es.config["correct"] == 1
    assert es.config["ability"] > 3.0  # correct -> ability up
    assert es.config["position"] == 1  # advanced
    assert es.config["next_question_id"]  # next item selected


def test_cat_submit_wrong_lowers_ability(db_session):
    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    _answer(db_session, es, actor, selected=[1], position=0)  # wrong
    assert es.config["ability"] < 3.0
    assert es.config["correct"] == 0


def test_cat_submit_records_ability_on_answer(db_session):
    from app.models.exam import ExamAnswer

    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    _answer(db_session, es, actor, selected=[0], position=0)
    ans = db_session.query(ExamAnswer).filter_by(session_id=es.id).one()
    assert ans.ability_estimate_after is not None
    assert ans.se_after is not None
    assert ans.ability_estimate_after > 3.0


def test_cat_submit_non_revisable(db_session):
    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    _answer(db_session, es, actor, selected=[0], position=0)  # position -> 1
    # re-submitting position 0 is now a position mismatch -> rejected (forward-only)
    with pytest.raises(svc.ValidationError):
        _answer(db_session, es, actor, selected=[0], position=0)


def test_cat_submit_position_mismatch_rejected(db_session):
    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    with pytest.raises(svc.ValidationError):
        _answer(db_session, es, actor, selected=[0], position=5)


def test_cat_terminate_at_max_items(db_session):
    from app.models.enums import ExamSessionStatus

    org, actor, es = _cat_start(db_session, early_stop=False, max_items=3, n_questions=5)
    ack0 = _answer(db_session, es, actor, selected=[0], position=0)
    assert ack0.finished is False
    ack1 = _answer(db_session, es, actor, selected=[0], position=1)
    assert ack1.finished is False
    ack2 = _answer(db_session, es, actor, selected=[0], position=2)
    assert ack2.finished is True  # reached max_items=3
    assert es.status == ExamSessionStatus.completed
    assert es.total_questions == 3
    assert es.correct_count == 3
    assert es.config["next_question_id"] is None


def test_cat_early_stop_converged_pass(db_session):
    from app.models.enums import ExamSessionStatus

    # passing_score=0 -> pass_ability=1.0; one correct answer -> ability 3.5,
    # CI entirely above 1.0 -> converged pass at min_items=1.
    org, actor, es = _cat_start(
        db_session, passing_score=0, min_items=1, max_items=10, early_stop=True)
    ack = _answer(db_session, es, actor, selected=[0], position=0)
    assert ack.finished is True
    assert es.status == ExamSessionStatus.completed
    assert es.total_questions == 1


def test_cat_early_stop_converged_fail(db_session):
    from app.models.enums import ExamSessionStatus

    # passing_score=1000 -> pass_ability=5.0; one wrong answer -> ability 2.5,
    # CI entirely below 5.0 -> converged fail at min_items=1.
    org, actor, es = _cat_start(
        db_session, passing_score=1000, min_items=1, max_items=10, early_stop=True)
    ack = _answer(db_session, es, actor, selected=[1], position=0)
    assert ack.finished is True
    assert es.status == ExamSessionStatus.completed


def test_cat_time_up_auto_submits(db_session):
    from datetime import datetime, timezone

    from app.models.enums import ExamSessionStatus

    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    es.config["deadline_at"] = datetime.now(timezone.utc).isoformat()
    flag_modified_for_test(es)
    db_session.flush()
    with pytest.raises(svc.ConflictError):
        svc.get_next_question(db_session, session_id=es.id, user_id=actor.id)
    assert db_session.get(ExamSession, es.id).status == ExamSessionStatus.auto_submitted
