"""#23: query-count bounds for the #13 N+1 hot paths.

Asserts a fixed upper bound on SELECT statements for each fixed hot path so an
N+1 regression turns a green test red (without these, N+1 passes silently).
Uses a ``before_cursor_execute`` listener on the test engine and seeds data
directly on the real ``cissp_test`` DB (same factory style as test_analytics).
"""
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.orm.attributes import flag_modified

from app.api.questions import list_questions
from app.dependencies import CurrentUser
from app.models.auth import Organization, User
from app.models.enums import (
    ExamSessionKind,
    ExamSessionStatus,
    OrgKind,
    PracticeSessionStatus,
    QuestionStatus,
    QuestionType,
    TextFormat,
)
from app.models.exam import ExamAnswer, ExamSession
from app.models.practice import PracticeAnswer, PracticeSession
from app.models.question import (
    Question,
    QuestionMapping,
    QuestionOption,
    QuestionTranslation,
)
from app.models.taxonomy import ExamBlueprint, ExamDomain
from app.services import analytics, exam, practice
from app.services.snapshot import snapshot_question


# --------------------------------------------------------------------------- #
# Minimal seed helpers (match the conventions in test_analytics.py)
# --------------------------------------------------------------------------- #

def _org(db, slug="qc"):
    org = Organization(name="QC", slug=slug, kind=OrgKind.personal)
    db.add(org)
    db.flush()
    return org


def _actor(db, org, email="qc@example.com"):
    u = User(email=email, password_hash="x", display_name="Q",
             default_organization_id=org.id)
    db.add(u)
    db.flush()
    return u


def _question(db, org, actor, *, stem="q"):
    q = Question(organization_id=org.id, question_type=QuestionType.single_choice,
                 status=QuestionStatus.published, available_languages=["en"],
                 created_by_id=actor.id)
    db.add(q)
    db.flush()
    db.add(QuestionOption(question_id=q.id, order_index=0, is_correct=True))
    db.add(QuestionOption(question_id=q.id, order_index=1, is_correct=False))
    db.add(QuestionTranslation(
        question_id=q.id, language="en", stem=stem, stem_format=TextFormat.markdown,
        correct_answer_rationale="r",
        options=[
            {"order_index": 0, "content": "A", "content_format": "markdown", "explanation": ""},
            {"order_index": 1, "content": "B", "content_format": "markdown", "explanation": ""},
        ],
    ))
    db.flush()
    return q


def _blueprint(db, version="v1"):
    bp = ExamBlueprint(version_label=version, effective_date="2026-04-15",
                       min_items=1, max_items=10, duration_minutes=30,
                       passing_score=700, max_score=1000, is_current=True)
    db.add(bp)
    db.flush()
    return bp


def _domain(db, bp, *, number, name, weight_pct):
    d = ExamDomain(blueprint_id=bp.id, number=number, name=name, weight_pct=weight_pct)
    db.add(d)
    db.flush()
    return d


def _map(db, question, domain):
    db.add(QuestionMapping(question_id=question.id, domain_id=domain.id))
    db.flush()


def _practice_session(db, org, actor):
    s = PracticeSession(user_id=actor.id, organization_id=org.id,
                        status=PracticeSessionStatus.completed, total_questions=1)
    db.add(s)
    db.flush()
    return s


def _exam_session(db, org, actor, bp):
    s = ExamSession(user_id=actor.id, organization_id=org.id, blueprint_id=bp.id,
                    session_kind=ExamSessionKind.fixed,
                    status=ExamSessionStatus.completed, total_questions=1)
    db.add(s)
    db.flush()
    return s


def _practice_answer(db, *, session, actor, question, is_correct):
    db.add(PracticeAnswer(
        session_id=session.id, user_id=actor.id, question_id=question.id,
        question_snapshot={}, options_snapshot=[], user_answer={"selected": [0]},
        is_correct=is_correct, time_spent_ms=1000,
        answered_at=datetime.now(timezone.utc),
    ))
    db.flush()


@contextmanager
def _count_selects(engine):
    """Count SELECT statements issued on the engine during the block.

    ``answer`` counts SELECTs touching the practice/exam answer tables, so the
    analytics test can assert ``_answer_rows`` runs exactly once.
    """
    counts = {"n": 0, "answer": 0}

    def before(conn, cursor, statement, params, context, executemany):
        s = (statement or "").strip().lower()
        if not s.startswith("select"):
            return
        counts["n"] += 1
        if "practice_answers" in s or "exam_answers" in s:
            counts["answer"] += 1

    event.listen(engine, "before_cursor_execute", before)
    try:
        yield counts
    finally:
        event.remove(engine, "before_cursor_execute", before)


# --------------------------------------------------------------------------- #
# Question list (#13: was 1 count + 1 list + N per-question _mappings_out)
# --------------------------------------------------------------------------- #

def test_list_questions_query_count_is_bounded(db_session, engine):
    org = _org(db_session, slug="qcl")
    actor = _actor(db_session, org)
    bp = _blueprint(db_session)
    dom = _domain(db_session, bp, number=1, name="D", weight_pct=100)
    for i in range(25):
        _map(db_session, _question(db_session, org, actor, stem=f"q{i}"), dom)
    db_session.flush()
    cu = CurrentUser(user=actor, org_id=org.id, roles=[], perms=[])

    with _count_selects(engine) as c:
        res = list_questions(
            page=1, size=25, status=None, question_type=None, difficulty=None,
            missing_language=None, search=None, domain_id=None, chapter_id=None,
            knowledge_point_id=None, tag_id=None, session=db_session, current=cu,
        )
    assert len(res["items"]) == 25
    # count + page list + one batched mapping lookup (was 1 + 1 + 25 = 27).
    assert c["n"] <= 5, f"expected <=5 SELECTs, got {c['n']}"


# --------------------------------------------------------------------------- #
# Exam review (#13: was session.get + answer query per item, 300+ for 150)
# --------------------------------------------------------------------------- #

def test_exam_review_query_count_is_bounded(db_session, engine):
    org = _org(db_session, slug="qcr")
    actor = _actor(db_session, org)
    bp = _blueprint(db_session)
    answered = [_question(db_session, org, actor, stem=f"a{i}") for i in range(12)]
    unanswered = [_question(db_session, org, actor, stem=f"u{i}") for i in range(3)]
    db_session.flush()
    es = _exam_session(db_session, org, actor, bp)
    es.config = {"question_ids": [str(q.id) for q in answered + unanswered]}
    flag_modified(es, "config")
    db_session.flush()
    for q in answered:
        opts = list(db_session.query(QuestionOption).filter_by(question_id=q.id).all())
        trans = list(db_session.query(QuestionTranslation).filter_by(question_id=q.id).all())
        snap = snapshot_question(q, trans, opts, language_mode="en")
        db_session.add(ExamAnswer(
            session_id=es.id, user_id=actor.id, question_id=q.id,
            question_snapshot=snap, options_snapshot=snap["options"],
            user_answer={"selected": [0]}, is_correct=True, time_spent_ms=1000,
            answered_at=datetime.now(timezone.utc),
        ))
    db_session.flush()

    with _count_selects(engine) as c:
        items = exam.get_review(session=db_session, session_id=es.id, user_id=actor.id)
    assert len(items) == 15
    # session load + batch answers + batch (questions/translations/options for
    # the 3 unanswered items). Was ~3 per item (45+).
    assert c["n"] <= 7, f"expected <=7 SELECTs, got {c['n']}"


# --------------------------------------------------------------------------- #
# Practice summary (#13: was one mapping query per answer + one per domain)
# --------------------------------------------------------------------------- #

def test_practice_summary_query_count_is_bounded(db_session, engine):
    org = _org(db_session, slug="qcp")
    actor = _actor(db_session, org)
    bp = _blueprint(db_session)
    dom = _domain(db_session, bp, number=1, name="D", weight_pct=100)
    ps = _practice_session(db_session, org, actor)
    for i in range(15):
        q = _question(db_session, org, actor, stem=f"p{i}")
        _map(db_session, q, dom)
        _practice_answer(db_session, session=ps, actor=actor, question=q,
                         is_correct=(i % 2 == 0))
    db_session.flush()

    with _count_selects(engine) as c:
        summary = practice._build_summary(db_session, ps)
    assert summary.answered_count == 15
    # answers + batched mappings + batched domain names (was 1 + 15 + 1).
    assert c["n"] <= 5, f"expected <=5 SELECTs, got {c['n']}"


# --------------------------------------------------------------------------- #
# Analytics personal_report (#13: was _answer_rows x~7 + full table scans)
# --------------------------------------------------------------------------- #

def test_personal_report_answer_rows_fetched_once(db_session, engine):
    org = _org(db_session, slug="qca")
    actor = _actor(db_session, org)
    bp = _blueprint(db_session)
    dom = _domain(db_session, bp, number=1, name="D", weight_pct=100)
    ps = _practice_session(db_session, org, actor)
    for i in range(20):
        q = _question(db_session, org, actor, stem=f"r{i}")
        _map(db_session, q, dom)
        _practice_answer(db_session, session=ps, actor=actor, question=q,
                         is_correct=(i % 2 == 0))
    db_session.flush()

    with _count_selects(engine) as c:
        analytics.personal_report(session=db_session, user_id=actor.id, blueprint=bp)
    # _answer_rows runs exactly once -> one practice_answers SELECT + one
    # exam_answers SELECT. The old code re-fetched ~7x (14 answer SELECTs).
    assert c["answer"] == 2, f"expected 2 answer-table SELECTs, got {c['answer']}"
    # overall bounded (old code was ~30 SELECTs).
    assert c["n"] <= 20, f"expected <=20 SELECTs, got {c['n']}"
