"""Service-layer tests for fixed + CAT exam API (translations-based).

Question content (stem, options, rationale) lives in per-language
``QuestionTranslation`` rows; the canonical ``QuestionOption`` carries only the
answer key (order_index + is_correct). Exam sessions resolve a language mode
(payload > user default > "en"), filter candidates by
``Question.available_languages`` (fixed assembly + CAT pool), and deliver /
answer / report / review bilingually.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.models.auth import Organization, User
from app.models.enums import (
    ExamSessionStatus,
    OrgKind,
    QuestionStatus,
    QuestionType,
    TextFormat,
)
from app.models.exam import ExamSession
from app.models.question import Question, QuestionOption, QuestionTranslation
from app.services import exam as svc
from sqlalchemy.orm.attributes import flag_modified


# --- fixtures / helpers ------------------------------------------------------


def _org(db_session, slug="t"):
    org = Organization(name="T", slug=slug, kind=OrgKind.personal)
    db_session.add(org)
    db_session.flush()
    return org


def _actor(db_session, org, email="learner@example.com", language_mode="en"):
    user = User(
        email=email,
        password_hash="x",
        display_name="L",
        default_organization_id=org.id,
        language_mode=language_mode,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _question(
    db_session,
    org,
    actor,
    *,
    langs=("en",),
    stem_suffix="",
    qtype=QuestionType.single_choice,
    difficulty=None,
    correct_indexes=(0,),
    n_opts=2,
):
    """Create a published question with translations for the given langs.

    ``langs`` is a subset of ("en", "zh") controlling which translations are
    created (and thus ``Question.available_languages``). Option correctness is
    set from ``correct_indexes`` on the canonical ``QuestionOption`` rows.
    """
    available = sorted(langs)
    q = Question(
        organization_id=org.id,
        question_type=qtype,
        status=QuestionStatus.published,
        difficulty=difficulty,
        available_languages=available,
        created_by_id=actor.id,
    )
    db_session.add(q)
    db_session.flush()
    for i in range(n_opts):
        db_session.add(
            QuestionOption(
                question_id=q.id,
                order_index=i,
                is_correct=(i in correct_indexes),
            )
        )
    en_opt_content = [("A", "en-A expl"), ("B", "en-B expl"), ("C", "en-C expl")]
    zh_opt_content = [("甲", "zh-甲 expl"), ("乙", "zh-乙 expl"), ("丙", "zh-丙 expl")]
    for lang in langs:
        if lang == "en":
            stem = f"en stem{stem_suffix}"
            rationale = f"en rationale{stem_suffix}"
            key_point = f"en key{stem_suffix}"
            opt_content = en_opt_content
        else:
            stem = f"中 stem{stem_suffix}"
            rationale = f"中 rationale{stem_suffix}"
            key_point = f"中 key{stem_suffix}"
            opt_content = zh_opt_content
        db_session.add(
            QuestionTranslation(
                question_id=q.id,
                language=lang,
                stem=stem,
                stem_format=TextFormat.markdown,
                correct_answer_rationale=rationale,
                key_point_summary=key_point,
                options=[
                    {
                        "order_index": i,
                        "content": opt_content[i][0],
                        "content_format": TextFormat.markdown.value,
                        "explanation": opt_content[i][1],
                    }
                    for i in range(n_opts)
                ],
            )
        )
    db_session.flush()
    return q


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


# --- session shape -----------------------------------------------------------


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


# --- fixed assembly + language-mode filtering --------------------------------


def test_assemble_weights_sum_to_count(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=4, max_items=10)
    d1 = _domain(db_session, bp, number=1, name="D1", weight_pct=50)
    d2 = _domain(db_session, bp, number=2, name="D2", weight_pct=50)
    for i in range(5):
        q = _question(db_session, org, actor, stem_suffix=f"a{i}")
        _map(db_session, q, d1)
    for i in range(5):
        q = _question(db_session, org, actor, stem_suffix=f"b{i}")
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
    assert es.config["language_mode"] == "en"  # default
    assert "deadline_at" in es.config


def test_assemble_redistributes_short_domain(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=4, max_items=10)
    d1 = _domain(db_session, bp, number=1, name="D1", weight_pct=50)
    d2 = _domain(db_session, bp, number=2, name="D2", weight_pct=50)
    # D1 has only 1 question but targets 2 -> shortfall filled from D2.
    q = _question(db_session, org, actor, stem_suffix="only1")
    _map(db_session, q, d1)
    for i in range(5):
        q = _question(db_session, org, actor, stem_suffix=f"d2-{i}")
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
    _question(db_session, org, actor, stem_suffix="solo")  # not mapped to d1
    # only 0 mapped published questions available but count=4
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
        _map(db_session, _question(db_session, org, actor, stem_suffix=f"q{i}"), d1)
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
        _map(db_session, _question(db_session, org, actor, stem_suffix=f"q{i}"), d1)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={},
    )
    assert es.total_questions == 3  # default = max_items


def test_en_mode_fixed_exam_excludes_zh_only(db_session):
    """en-mode fixed assembly only includes en-capable questions (en-only +
    bilingual), excluding zh-only questions."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=1, max_items=10)
    d = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    en_only = _question(db_session, org, actor, langs=("en",), stem_suffix=" en")
    zh_only = _question(db_session, org, actor, langs=("zh",), stem_suffix=" zh")
    both = _question(db_session, org, actor, langs=("en", "zh"), stem_suffix=" both")
    for q in (en_only, zh_only, both):
        _map(db_session, q, d)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload={"count": 2, "language_mode": "en"},
    )
    ids = set(es.config["question_ids"])
    assert str(en_only.id) in ids
    assert str(both.id) in ids
    assert str(zh_only.id) not in ids
    assert es.config["language_mode"] == "en"


def test_bilingual_mode_fixed_exam_requires_both(db_session):
    """bilingual-mode fixed assembly only includes questions with en + zh."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=1, max_items=10)
    d = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    en_only = _question(db_session, org, actor, langs=("en",), stem_suffix=" en")
    zh_only = _question(db_session, org, actor, langs=("zh",), stem_suffix=" zh")
    both = _question(db_session, org, actor, langs=("en", "zh"), stem_suffix=" both")
    for q in (en_only, zh_only, both):
        _map(db_session, q, d)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload={"count": 1, "language_mode": "bilingual"},
    )
    ids = set(es.config["question_ids"])
    assert ids == {str(both.id)}


def test_fixed_exam_uses_user_default_language_mode(db_session):
    """When the payload omits language_mode, the user's default is used."""
    org = _org(db_session)
    actor = _actor(db_session, org, language_mode="zh")
    bp = _blueprint(db_session, min_items=1, max_items=10)
    d = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    en_only = _question(db_session, org, actor, langs=("en",), stem_suffix=" en")
    zh_only = _question(db_session, org, actor, langs=("zh",), stem_suffix=" zh")
    for q in (en_only, zh_only):
        _map(db_session, q, d)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"count": 1},
    )
    assert es.config["language_mode"] == "zh"
    ids = set(es.config["question_ids"])
    assert str(zh_only.id) in ids
    assert str(en_only.id) not in ids


# --- fixed delivery / answer / finish ---------------------------------------


def _start(db_session, org, actor, *, count=1, bp=None, language_mode=None):
    if bp is None:
        bp = _blueprint(db_session, min_items=1, max_items=10)
        d = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
        q = _question(db_session, org, actor, stem_suffix="q1")
        _map(db_session, q, d)
    payload = {"count": count}
    if language_mode is not None:
        payload["language_mode"] = language_mode
    return svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload=payload,
    )


def test_delivery_is_bilingual_and_strips_correctness(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    s = _start(db_session, org, actor, count=1)
    out = svc.get_question_at(
        db_session, session_id=s.id, position=0, user_id=actor.id
    )
    assert out["position"] == 0
    assert out["total"] == 1
    assert out["language_mode"] == "en"
    assert out["available_languages"] == ["en"]
    assert out["stem"] == {"en": "en stemq1", "zh": None}
    for opt in out["options"]:
        assert "is_correct" not in opt
        assert set(opt["content"].keys()) == {"en", "zh"}
    assert out["time_remaining_ms"] > 0
    assert out["elapsed_ms"] >= 0
    assert out["previous_answer"] is None


def test_delivery_bilingual_question_returns_both_languages(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=1, max_items=10)
    d = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    q = _question(db_session, org, actor, langs=("en", "zh"), stem_suffix=" bi")
    _map(db_session, q, d)
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload={"count": 1, "language_mode": "bilingual"},
    )
    out = svc.get_question_at(
        db_session, session_id=s.id, position=0, user_id=actor.id
    )
    assert out["available_languages"] == ["en", "zh"]
    assert out["language_mode"] == "bilingual"
    assert out["stem"] == {"en": "en stem bi", "zh": "中 stem bi"}
    assert out["options"][0]["content"] == {"en": "A", "zh": "甲"}
    assert out["options"][1]["content"] == {"en": "B", "zh": "乙"}


def test_submit_answer_returns_ack_no_judgment(db_session):
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


def test_answer_snapshot_records_mode_and_translations(db_session):
    """The frozen exam snapshot records the delivered language_mode + all
    translations (NFR-DATA-01)."""
    from app.models.exam import ExamAnswer

    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=1, max_items=10)
    d = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    q = _question(db_session, org, actor, langs=("en", "zh"), stem_suffix=" bi")
    _map(db_session, q, d)
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload={"count": 1, "language_mode": "bilingual"},
    )
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    ans = db_session.query(ExamAnswer).filter_by(session_id=s.id).one()
    snap = ans.question_snapshot
    assert snap["language_mode"] == "bilingual"
    assert set(snap["translations"].keys()) == {"en", "zh"}
    assert snap["translations"]["en"]["stem"] == "en stem bi"
    assert snap["translations"]["zh"]["stem"] == "中 stem bi"
    # canonical answer key frozen on options_snapshot
    assert [o["order_index"] for o in ans.options_snapshot] == [0, 1]
    assert [o["is_correct"] for o in ans.options_snapshot] == [True, False]


def test_delivery_returns_previous_answer(db_session):
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
    # Bilingual so wrong-question / review stems render Localized {en,zh}.
    q1 = _question(db_session, org, actor, langs=("en", "zh"), stem_suffix="right")  # 0 correct
    q2 = _question(db_session, org, actor, langs=("en", "zh"), stem_suffix="wrong")  # 0 correct
    _map(db_session, q1, d)
    _map(db_session, q2, d)
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"count": 2},
    )
    return org, actor, s, (q1, q2)


def test_finish_recomputes_correct_count_and_score(db_session):
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


def test_report_wrong_question_stem_is_bilingual(db_session):
    """Wrong-question stems in the report are Localized {en,zh} from snapshot."""
    org, actor, s, _ = _two_question_exam(db_session)
    # Bilingual questions: answer one wrong to produce a wrong question.
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
    report = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert len(report.wrong_questions) == 2
    for wq in report.wrong_questions:
        assert set(wq.stem.model_dump().keys()) == {"en", "zh"}
        assert wq.stem.en is not None
        assert wq.stem.zh is not None


def test_finish_per_domain_performance(db_session):
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
    org, actor, s, _ = _two_question_exam(db_session, passing_score=0, max_score=1000)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    report = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert report.passed is True  # 500 >= 0


def test_finish_recomputes_after_revision(db_session):
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
    org, actor, s, _ = _two_question_exam(db_session)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    report = svc.get_report(db_session, session_id=s.id, user_id=actor.id)
    assert report.correct_count == 1


# --- fixed review ------------------------------------------------------------


def test_review_only_after_finish(db_session):
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


def test_review_is_bilingual_answered(db_session):
    """Review items for answered questions render Localized stem/options/
    rationale from the snapshot."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=1, max_items=1)
    d = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    q = _question(db_session, org, actor, langs=("en", "zh"), stem_suffix=" bi")
    _map(db_session, q, d)
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload={"count": 1, "language_mode": "bilingual"},
    )
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    review = svc.get_review(db_session, session_id=s.id, user_id=actor.id)
    assert len(review) == 1
    item = review[0]
    assert item.available_languages == ["en", "zh"]
    assert item.stem.model_dump() == {"en": "en stem bi", "zh": "中 stem bi"}
    assert len(item.options) == 2
    assert item.options[0].content.model_dump() == {"en": "A", "zh": "甲"}
    assert item.options[0].explanation.model_dump() == {"en": "en-A expl", "zh": "zh-甲 expl"}
    assert item.options[0].is_correct is True
    assert item.options[1].is_correct is False
    assert item.correct_rationale.model_dump() == {"en": "en rationale bi", "zh": "中 rationale bi"}
    assert item.key_point_summary.model_dump() == {"en": "en key bi", "zh": "中 key bi"}
    assert item.your_answer["is_correct"] is True


def test_review_reads_correctness_from_snapshot(db_session):
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


def test_review_never_answered_is_bilingual_from_live(db_session):
    """A question that was never answered (lazy auto-submit / manual finish
    mid-exam) renders Localized stem/options/rationale from LIVE translations
    (not a snapshot, which does not exist for unanswered items).

    Shuffle-independent: the skipped question is identified from
    config['question_ids'][1] after assembly, then its live en stem is mutated
    to prove the review reads live translations rather than a frozen view."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = _blueprint(db_session, min_items=2, max_items=2)
    d = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    q1 = _question(db_session, org, actor, langs=("en", "zh"), stem_suffix=" one")
    q2 = _question(db_session, org, actor, langs=("en", "zh"), stem_suffix=" two")
    _map(db_session, q1, d)
    _map(db_session, q2, d)
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload={"count": 2, "language_mode": "bilingual"},
    )
    # Answer only position 0; position 1 is never answered.
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    # Identify the skipped question (position 1) and mutate its LIVE en stem.
    skipped_qid = uuid.UUID(s.config["question_ids"][1])
    skipped_tr = db_session.query(QuestionTranslation).filter_by(
        question_id=skipped_qid, language="en").one()
    skipped_tr.stem = "MUTATED LIVE STEM"
    db_session.flush()
    svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    review = svc.get_review(db_session, session_id=s.id, user_id=actor.id)
    assert len(review) == 2
    skipped = next(r for r in review if r.your_answer is None)
    assert skipped.time_spent_ms is None
    assert skipped.question_id == skipped_qid
    assert skipped.available_languages == ["en", "zh"]
    # stem comes from live translations (mutated value visible -> live read)
    assert skipped.stem.en == "MUTATED LIVE STEM"
    assert skipped.stem.zh is not None
    # options carry Localized content + explanation from live translations
    assert len(skipped.options) == 2
    for opt in skipped.options:
        assert set(opt.content.model_dump().keys()) == {"en", "zh"}
        assert opt.content.en is not None
        assert opt.content.zh is not None
        assert set(opt.explanation.model_dump().keys()) == {"en", "zh"}
    # rationale + key_point are Localized from live translations
    assert skipped.correct_rationale.en is not None
    assert skipped.correct_rationale.zh is not None
    assert skipped.key_point_summary.en is not None
    assert skipped.key_point_summary.zh is not None


# --- history -----------------------------------------------------------------


def test_history_ordered_and_only_finished(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    # first exam: 1 question, finished
    bp1 = _blueprint(db_session, min_items=1, max_items=1, version="v1")
    d1 = _domain(db_session, bp1, number=1, name="D1", weight_pct=100)
    q = _question(db_session, org, actor, stem_suffix="q")
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


# --- CAT: candidate filtering + config --------------------------------------


def _cat_blueprint(db_session, *, min_items=1, max_items=5, passing_score=700,
                   max_score=1000, duration_minutes=30):
    bp = _blueprint(
        db_session, min_items=min_items, max_items=max_items,
        passing_score=passing_score, max_score=max_score,
        duration_minutes=duration_minutes, version="cat-v1",
    )
    d1 = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    return bp, d1


def _seed_cat_questions(db_session, org, actor, domain, n=5, difficulty=3,
                        langs=("en",)):
    qs = []
    for i in range(n):
        q = _question(
            db_session, org, actor, stem_suffix=f" cat-q{i}",
            difficulty=difficulty, langs=langs,
        )
        _map(db_session, q, domain)
        qs.append(q)
    return qs


def test_create_cat_session_medium_start_and_config_shape(db_session):
    from app.models.enums import ExamSessionKind

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
    assert cfg["language_mode"] == "en"  # default mode stamped
    assert "deadline_at" in cfg
    assert "disclaimer" in cfg
    assert "cat_params" in cfg


def test_create_cat_first_item_is_medium_difficulty(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(db_session, min_items=1, max_items=5)
    qs = _seed_cat_questions(db_session, org, actor, d1, n=5, difficulty=3)
    # add a couple of extreme-difficulty items that must NOT be chosen first
    hard = _question(db_session, org, actor, stem_suffix="hard", difficulty=5)
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


def test_cat_pool_excludes_missing_language(db_session):
    """en-mode CAT pool excludes zh-only questions; the first item is en-capable."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(db_session, min_items=1, max_items=5)
    en_qs = _seed_cat_questions(db_session, org, actor, d1, n=3, difficulty=3, langs=("en",))
    zh_only = _question(db_session, org, actor, stem_suffix=" zh-only", difficulty=3, langs=("zh",))
    _map(db_session, zh_only, d1)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload={"kind": "cat", "language_mode": "en"},
    )
    assert es.config["language_mode"] == "en"
    first_id = uuid.UUID(es.config["next_question_id"])
    assert first_id != zh_only.id
    assert first_id in {q.id for q in en_qs}
    # answering advances without ever picking the zh-only question
    ack = svc.submit_answer(
        db_session, session_id=es.id, user_id=actor.id,
        payload={"position": 0, "selected": [0],
                 "started_at": datetime.now(timezone.utc)},
    )
    if not ack.finished:
        next_id = uuid.UUID(es.config["next_question_id"])
        assert next_id != zh_only.id


def test_get_next_question_is_bilingual(db_session):
    """CAT /next delivery is bilingual: Localized stem/options, no answer key."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(db_session, min_items=1, max_items=5)
    _seed_cat_questions(db_session, org, actor, d1, n=5, difficulty=3, langs=("en", "zh"))
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload={"kind": "cat", "language_mode": "bilingual"},
    )
    out = svc.get_next_question(db_session, session_id=es.id, user_id=actor.id)
    assert out["position"] == 0
    assert out["total"] == 5
    assert out["language_mode"] == "bilingual"
    assert set(out["stem"].keys()) == {"en", "zh"}
    assert out["stem"]["en"] is not None
    assert out["stem"]["zh"] is not None
    for opt in out["options"]:
        assert "is_correct" not in opt
        assert set(opt["content"].keys()) == {"en", "zh"}
        assert opt["content"]["en"] is not None
        assert opt["content"]["zh"] is not None
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
               early_stop=True, language_mode=None):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(
        db_session, min_items=min_items, max_items=max_items,
        passing_score=passing_score, max_score=max_score,
    )
    # Seed questions that satisfy the requested mode (bilingual mode requires
    # questions with both en + zh translations).
    langs = ("en", "zh") if language_mode == "bilingual" else ("en",)
    _seed_cat_questions(
        db_session, org, actor, d1, n=n_questions, difficulty=difficulty, langs=langs,
    )
    payload = {"kind": "cat"}
    if language_mode is not None:
        payload["language_mode"] = language_mode
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload=payload
    )
    if not early_stop:
        es.config["cat_params"]["early_stop_enabled"] = False
        flag_modified(es, "config")
    return org, actor, es


def _answer(db_session, es, actor, *, selected, position):
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
    # passing_score=0 -> pass_ability=1.0; one correct answer -> ability 3.5,
    # CI entirely above 1.0 -> converged pass at min_items=1.
    org, actor, es = _cat_start(
        db_session, passing_score=0, min_items=1, max_items=10, early_stop=True)
    ack = _answer(db_session, es, actor, selected=[0], position=0)
    assert ack.finished is True
    assert es.status == ExamSessionStatus.completed
    assert es.total_questions == 1


def test_cat_early_stop_converged_fail(db_session):
    # passing_score=1000 -> pass_ability=5.0; one wrong answer -> ability 2.5,
    # CI entirely below 5.0 -> converged fail at min_items=1.
    org, actor, es = _cat_start(
        db_session, passing_score=1000, min_items=1, max_items=10, early_stop=True)
    ack = _answer(db_session, es, actor, selected=[1], position=0)
    assert ack.finished is True
    assert es.status == ExamSessionStatus.completed


def test_cat_time_up_auto_submits(db_session):
    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    es.config["deadline_at"] = datetime.now(timezone.utc).isoformat()
    flag_modified(es, "config")
    db_session.flush()
    with pytest.raises(svc.ConflictError):
        svc.get_next_question(db_session, session_id=es.id, user_id=actor.id)
    assert db_session.get(ExamSession, es.id).status == ExamSessionStatus.auto_submitted


def test_cat_time_up_history_shows_answered_totals(db_session):
    """I-1: auto-submitted (time-up) CAT sessions must not show stale
    total_questions=0 / correct_count=0 / accuracy=0.0 in /history."""
    from app.services import cat_engine

    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    # Answer one question correctly (option 0 is correct on every seeded q).
    _answer(db_session, es, actor, selected=[0], position=0)
    answered = es.config["answered"]
    correct = es.config["correct"]
    assert answered >= 1
    assert correct == 1
    # Force time-up: deadline into the past, then touch a path that runs
    # _auto_submit_if_expired.
    es.config["deadline_at"] = datetime.now(timezone.utc).isoformat()
    flag_modified(es, "config")
    db_session.flush()
    with pytest.raises(svc.ConflictError):
        svc.get_next_question(db_session, session_id=es.id, user_id=actor.id)
    assert db_session.get(ExamSession, es.id).status == ExamSessionStatus.auto_submitted
    # The stored columns stay stale (auto-submit does not reconcile them).
    assert es.total_questions == 0
    assert es.correct_count == 0
    # History must reflect the answers actually given, not the stale columns.
    hist = svc.list_history(db_session, user_id=actor.id)
    assert len(hist) == 1
    row = hist[0]
    assert row.total_questions == answered
    assert row.correct_count == correct
    assert row.accuracy == correct / answered
    # Regression guard: ability-based scoring fields remain correct.
    expected_scaled = cat_engine.scaled_score(
        es.config["ability"], es.config["max_score"])
    assert row.scaled_score == expected_scaled
    assert row.max_score == 1000
    assert row.passed == (expected_scaled >= es.config["passing_score"])


def _finish_cat(db_session, *, passing_score=700, max_score=1000, selected=0,
                early_stop=False, max_items=3, n_questions=5):
    org, actor, es = _cat_start(
        db_session, passing_score=passing_score, max_score=max_score,
        early_stop=early_stop, max_items=max_items, n_questions=n_questions,
    )
    pos = 0
    ack = _answer(db_session, es, actor, selected=[selected], position=pos)
    while not ack.finished:
        pos += 1
        ack = _answer(db_session, es, actor, selected=[selected], position=pos)
    return org, actor, es


def test_cat_report_carries_ability_and_disclaimer(db_session):
    org, actor, es = _finish_cat(db_session, early_stop=False, max_items=3)
    report = svc.get_report(db_session, session_id=es.id, user_id=actor.id)
    assert report.ability_estimate is not None
    assert report.sem is not None
    assert report.ability_ci_lower is not None
    assert report.ability_ci_upper is not None
    assert report.readiness_level in {"ready", "almost_ready", "developing", "needs_work"}
    assert report.disclaimer  # FR-CAT-10
    # ability-based scoring: all correct -> ability high -> scaled > 500
    assert report.scaled_score > 500
    assert report.total_questions == 3


def test_cat_report_pass_line_is_ability_based(db_session):
    # passing_score=1000 -> pass_ability=5.0; even all-correct cannot reach 5.0
    # exactly, so a 3-item run stays below -> passed False.
    org, actor, es = _finish_cat(
        db_session, passing_score=1000, max_score=1000,
        early_stop=False, max_items=3, selected=0)
    report = svc.get_report(db_session, session_id=es.id, user_id=actor.id)
    assert report.passed is False


def test_cat_report_wrong_questions_bilingual(db_session):
    """CAT report wrong-questions render Localized {en,zh} stems from snapshots."""
    org, actor, es = _cat_start(
        db_session, early_stop=False, max_items=3, n_questions=5,
        language_mode="bilingual",
    )
    # answer all wrong (select option 1, but option 0 is correct)
    pos = 0
    ack = _answer(db_session, es, actor, selected=[1], position=pos)
    while not ack.finished:
        pos += 1
        ack = _answer(db_session, es, actor, selected=[1], position=pos)
    svc.finish_session(db_session, session_id=es.id, user_id=actor.id)
    report = svc.get_report(db_session, session_id=es.id, user_id=actor.id)
    assert len(report.wrong_questions) == pos + 1
    for wq in report.wrong_questions:
        assert set(wq.stem.model_dump().keys()) == {"en", "zh"}
        assert wq.stem.en is not None
        assert wq.stem.zh is not None


def test_cat_review_is_snapshot_graded(db_session):
    org, actor, es = _cat_start(db_session, early_stop=False, max_items=3, n_questions=5)
    _answer(db_session, es, actor, selected=[0], position=0)
    # mutate the live first question's options
    first_qid = uuid.UUID(es.config["question_ids"][0])
    opt0 = db_session.query(QuestionOption).filter_by(
        question_id=first_qid, order_index=0).one()
    opt1 = db_session.query(QuestionOption).filter_by(
        question_id=first_qid, order_index=1).one()
    opt0.is_correct = False
    opt1.is_correct = True
    db_session.flush()
    # finish by answering remaining
    ack = _answer(db_session, es, actor, selected=[0], position=1)
    if not ack.finished:
        _answer(db_session, es, actor, selected=[0], position=2)
    svc.finish_session(db_session, session_id=es.id, user_id=actor.id)
    review = svc.get_review(db_session, session_id=es.id, user_id=actor.id)
    item0 = review[0]
    # snapshot still says order_index 0 was correct
    assert item0.options[0].is_correct is True
    assert item0.options[1].is_correct is False
    assert item0.your_answer["is_correct"] is True  # judged against snapshot


def test_cat_review_is_bilingual(db_session):
    """CAT review items render Localized stem/options/rationale from snapshots."""
    org, actor, es = _cat_start(
        db_session, early_stop=False, max_items=3, n_questions=5,
        language_mode="bilingual",
    )
    pos = 0
    ack = _answer(db_session, es, actor, selected=[0], position=pos)
    while not ack.finished:
        pos += 1
        ack = _answer(db_session, es, actor, selected=[0], position=pos)
    svc.finish_session(db_session, session_id=es.id, user_id=actor.id)
    review = svc.get_review(db_session, session_id=es.id, user_id=actor.id)
    assert len(review) == pos + 1
    for item in review:
        assert set(item.stem.model_dump().keys()) == {"en", "zh"}
        assert item.stem.en is not None
        assert item.stem.zh is not None
        assert item.available_languages == ["en", "zh"]
        for opt in item.options:
            assert set(opt.content.model_dump().keys()) == {"en", "zh"}
            assert opt.content.en is not None
            assert opt.content.zh is not None
        assert item.correct_rationale.en is not None
        assert item.correct_rationale.zh is not None


def test_cat_finish_manual_when_in_progress(db_session):
    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5, n_questions=5)
    _answer(db_session, es, actor, selected=[0], position=0)
    # manually finish mid-exam
    report = svc.finish_session(db_session, session_id=es.id, user_id=actor.id)
    assert db_session.get(ExamSession, es.id).status == ExamSessionStatus.completed
    assert es.total_questions == 1
    assert report.total_questions == 1


def test_cat_history_ability_based(db_session):
    org, actor, es = _finish_cat(db_session, early_stop=False, max_items=3, selected=0)
    hist = svc.list_history(db_session, user_id=actor.id)
    assert len(hist) == 1
    # all correct -> ability high -> scaled > 500 (ability-based, not raw)
    assert hist[0].scaled_score > 500
    assert hist[0].total_questions == 3


def test_cat_history_excludes_in_progress(db_session):
    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    # leave in progress
    assert svc.list_history(db_session, user_id=actor.id) == []


def test_cat_session_snapshots_current_cat_params(db_session):
    """NFR-DATA-01: a new CAT session snapshots the current CatParamsVersion
    into config["cat_params"] so later edits to the version never change
    existing sessions."""
    from datetime import date

    from app.models.admin import CatParamsVersion

    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(db_session, min_items=1, max_items=5)
    _seed_cat_questions(db_session, org, actor, d1, n=5, difficulty=3)
    cpv = CatParamsVersion(
        version_label="v1", effective_date=date(2026, 1, 1),
        is_current=True,
        params={"k0": 0.42, "decay": 0.1, "base_se": 1.0,
                "early_stop_enabled": True},
    )
    db_session.add(cpv); db_session.flush()
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"kind": "cat"}
    )
    assert es.config["cat_params"]["k0"] == 0.42
    assert es.config["cat_params"]["early_stop_enabled"] is True
    # mutating the live version after session creation does NOT change the
    # snapshot already stored on the session (historical integrity).
    cpv.params["k0"] = 0.99
    db_session.flush()
    assert es.config["cat_params"]["k0"] == 0.42


def test_cat_session_falls_back_to_default_params(db_session):
    """Without a CatParamsVersion, config["cat_params"] falls back to
    cat_engine.DEFAULT_PARAMS (the default test state)."""
    from app.services import cat_engine

    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(db_session, min_items=1, max_items=5)
    _seed_cat_questions(db_session, org, actor, d1, n=5, difficulty=3)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"kind": "cat"}
    )
    assert es.config["cat_params"]["k0"] == cat_engine.DEFAULT_PARAMS["k0"]
    assert es.config["cat_params"] == dict(cat_engine.DEFAULT_PARAMS)
