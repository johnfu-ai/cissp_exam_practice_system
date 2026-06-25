"""Service-layer tests for practice API (translations-based).

Question content (stem, options, rationale) lives in per-language
``QuestionTranslation`` rows; the canonical ``QuestionOption`` carries only the
answer key (order_index + is_correct). Practice sessions resolve a language
mode (payload > user default > "en"), filter candidates by
``Question.available_languages``, and deliver/answer/summarize bilingually.
"""

from datetime import datetime, timezone

import pytest

from app.models.auth import Organization, User
from app.models.enums import (
    ErrorType,
    OrgKind,
    PracticeSessionStatus,
    QuestionStatus,
    QuestionType,
    TextFormat,
)
from app.models.practice import PracticeAnswer, PracticeSession, UserQuestionState
from app.models.question import Question, QuestionOption, QuestionTranslation
from app.schemas.practice import (
    AnswerIn,
    QuestionStateIn,
    SessionCreateIn,
)
from app.services import practice as svc


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
            opt_content = en_opt_content
        else:
            stem = f"中 stem{stem_suffix}"
            rationale = f"中 rationale{stem_suffix}"
            opt_content = zh_opt_content
        db_session.add(
            QuestionTranslation(
                question_id=q.id,
                language=lang,
                stem=stem,
                stem_format=TextFormat.markdown,
                correct_answer_rationale=rationale,
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


def _start(db_session, org, actor, count=1, **kw):
    return svc.create_session(
        db_session,
        org_id=org.id,
        actor_id=actor.id,
        payload=SessionCreateIn(count=count, order_mode="sequential", **kw),
    )


# --- session creation + candidate filtering ---------------------------------


def test_session_has_config_and_paused_at_columns(db_session):
    """PracticeSession must expose config (JSONB) and paused_at columns."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor)
    session = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=1),
    )
    assert session.config is not None
    assert "question_ids" in session.config
    assert "language_mode" in session.config
    assert session.paused_at is None
    assert session.status == PracticeSessionStatus.in_progress


def test_create_session_random_pick(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    for i in range(5):
        _question(db_session, org, actor, stem_suffix=f" {i}")
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=3),
    )
    assert s.total_questions == 3
    assert len(s.config["question_ids"]) == 3
    assert s.config["subset"] == "all"
    assert s.config["order_mode"] == "random"


def test_create_session_scope_by_domain(db_session):
    from app.models.question import QuestionMapping
    from app.models.taxonomy import ExamBlueprint, ExamDomain

    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = ExamBlueprint(version_label="v1", effective_date="2026-04-15",
                       min_items=100, max_items=150, duration_minutes=180,
                       passing_score=700, max_score=1000, is_current=False)
    db_session.add(bp)
    db_session.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=10)
    db_session.add(dom)
    db_session.flush()
    in_q = _question(db_session, org, actor, stem_suffix=" in")
    _question(db_session, org, actor, stem_suffix=" out")
    db_session.add(QuestionMapping(question_id=in_q.id, domain_id=dom.id))
    db_session.flush()
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=10, domain_id=dom.id),
    )
    assert s.total_questions == 1
    assert s.config["question_ids"] == [str(in_q.id)]


def test_create_session_empty_scope_rejected(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    with pytest.raises(svc.ValidationError):
        svc.create_session(
            db_session, org_id=org.id, actor_id=actor.id,
            payload=SessionCreateIn(count=10),
        )


def test_create_session_subset_unpracticed(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    q1 = _question(db_session, org, actor, stem_suffix=" done")
    q2 = _question(db_session, org, actor, stem_suffix=" new")
    other = PracticeSession(
        user_id=actor.id, organization_id=org.id,
        status=PracticeSessionStatus.completed, total_questions=1,
    )
    db_session.add(other)
    db_session.flush()
    db_session.add(PracticeAnswer(
        session_id=other.id, user_id=actor.id, question_id=q1.id,
        question_snapshot={}, options_snapshot=[], user_answer={"selected": [0]},
        is_correct=True,
    ))
    db_session.flush()
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=10, subset="unpracticed", order_mode="sequential"),
    )
    assert s.config["question_ids"] == [str(q2.id)]


def test_create_session_scope_by_chapter(db_session):
    from app.models.question import Book, Chapter, QuestionMapping

    org = _org(db_session)
    actor = _actor(db_session, org)
    book = Book(organization_id=org.id, title="B")
    db_session.add(book)
    db_session.flush()
    ch = Chapter(organization_id=org.id, book_id=book.id, order_index=0, title="C1")
    db_session.add(ch)
    db_session.flush()
    in_q = _question(db_session, org, actor, stem_suffix=" in")
    _question(db_session, org, actor, stem_suffix=" out")
    db_session.add(QuestionMapping(question_id=in_q.id, chapter_id=ch.id))
    db_session.flush()
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=10, chapter_ids=[ch.id], order_mode="sequential"),
    )
    assert s.config["question_ids"] == [str(in_q.id)]


def test_en_mode_excludes_zh_only_question(db_session):
    """en-mode session only contains en-capable questions (en-only + bilingual),
    excluding zh-only questions."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    en_only = _question(db_session, org, actor, langs=("en",), stem_suffix=" en-only")
    zh_only = _question(db_session, org, actor, langs=("zh",), stem_suffix=" zh-only")
    both = _question(db_session, org, actor, langs=("en", "zh"), stem_suffix=" both")
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=10, language_mode="en", order_mode="sequential"),
    )
    ids = set(s.config["question_ids"])
    assert str(en_only.id) in ids
    assert str(both.id) in ids
    assert str(zh_only.id) not in ids
    assert s.config["language_mode"] == "en"


def test_zh_mode_excludes_en_only_question(db_session):
    """zh-mode session only contains zh-capable questions."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    en_only = _question(db_session, org, actor, langs=("en",), stem_suffix=" en-only")
    zh_only = _question(db_session, org, actor, langs=("zh",), stem_suffix=" zh-only")
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=10, language_mode="zh", order_mode="sequential"),
    )
    ids = set(s.config["question_ids"])
    assert str(zh_only.id) in ids
    assert str(en_only.id) not in ids
    assert s.config["language_mode"] == "zh"


def test_bilingual_mode_requires_both_languages(db_session):
    """bilingual-mode session only contains questions with both en + zh."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    en_only = _question(db_session, org, actor, langs=("en",), stem_suffix=" en-only")
    zh_only = _question(db_session, org, actor, langs=("zh",), stem_suffix=" zh-only")
    both = _question(db_session, org, actor, langs=("en", "zh"), stem_suffix=" both")
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=10, language_mode="bilingual", order_mode="sequential"),
    )
    ids = set(s.config["question_ids"])
    assert ids == {str(both.id)}
    assert str(en_only.id) not in ids
    assert str(zh_only.id) not in ids


def test_session_uses_user_default_language_mode_when_payload_omits(db_session):
    """When the payload omits language_mode, the user's default is used for both
    the config stamp and candidate filtering."""
    org = _org(db_session)
    actor = _actor(db_session, org, language_mode="zh")
    en_only = _question(db_session, org, actor, langs=("en",), stem_suffix=" en-only")
    zh_only = _question(db_session, org, actor, langs=("zh",), stem_suffix=" zh-only")
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=10, order_mode="sequential"),
    )
    assert s.config["language_mode"] == "zh"
    ids = set(s.config["question_ids"])
    assert str(zh_only.id) in ids
    assert str(en_only.id) not in ids


# --- delivery ----------------------------------------------------------------


def test_get_question_strips_correctness(db_session):
    """Delivery never leaks the answer key (no is_correct on options)."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor, langs=("en",), stem_suffix=" q1")
    s = _start(db_session, org, actor)
    out = svc.get_question_at(
        db_session, session_id=s.id, position=0, user_id=actor.id
    )
    assert out["position"] == 0
    assert out["total"] == 1
    assert out["stem"] == {"en": "en stem q1", "zh": None}
    assert out["language_mode"] == "en"
    assert out["available_languages"] == ["en"]
    for opt in out["options"]:
        assert "is_correct" not in opt


def test_delivery_returns_both_languages(db_session):
    """Bilingual question delivery returns stem {en,zh} and option content {en,zh}."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor, langs=("en", "zh"), stem_suffix=" bi")
    s = _start(db_session, org, actor)
    out = svc.get_question_at(
        db_session, session_id=s.id, position=0, user_id=actor.id
    )
    assert out["available_languages"] == ["en", "zh"]
    assert out["stem"] == {"en": "en stem bi", "zh": "中 stem bi"}
    assert len(out["options"]) == 2
    for opt in out["options"]:
        assert set(opt["content"].keys()) == {"en", "zh"}
        assert opt["content"]["en"] is not None
        assert opt["content"]["zh"] is not None
        assert opt["content_format"]["en"] == "markdown"
        assert opt["content_format"]["zh"] == "markdown"
    # option 0 content matches the seeded translation content
    assert out["options"][0]["content"] == {"en": "A", "zh": "甲"}
    assert out["options"][1]["content"] == {"en": "B", "zh": "乙"}


# --- answer ------------------------------------------------------------------


def test_submit_answer_judges_from_snapshot(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor)  # option 0 correct
    s = _start(db_session, org, actor)
    result = svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    assert result.is_correct is True
    assert result.correct_indexes == [0]
    assert result.selected_indexes == [0]


def test_submit_answer_incorrect(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor)  # 0 correct
    s = _start(db_session, org, actor)
    result = svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[1], started_at=datetime.now(timezone.utc)),
    )
    assert result.is_correct is False
    assert s.correct_count == 0


def test_submit_answer_multiple_choice(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(
        db_session, org, actor, stem_suffix=" multi",
        qtype=QuestionType.multiple_choice,
        correct_indexes=(0, 1), n_opts=3,
    )
    s = _start(db_session, org, actor)
    r1 = svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    assert r1.is_correct is False


def test_submit_answer_returns_bilingual_rationale(db_session):
    """AnswerResultOut rationale/per-option explanation are Localized {en,zh}."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor, langs=("en", "zh"), stem_suffix=" bi")
    s = _start(db_session, org, actor)
    result = svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    assert result.correct_rationale.model_dump() == {"en": "en rationale bi", "zh": "中 rationale bi"}
    assert result.key_point_summary.model_dump() == {"en": None, "zh": None}
    assert len(result.per_option) == 2
    for pe in result.per_option:
        assert set(pe.explanation.model_dump().keys()) == {"en", "zh"}
    assert result.per_option[0].explanation.model_dump() == {"en": "en-A expl", "zh": "zh-甲 expl"}
    assert result.per_option[1].explanation.model_dump() == {"en": "en-B expl", "zh": "zh-乙 expl"}


def test_submit_answer_persists_snapshot(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    q = _question(db_session, org, actor, langs=("en", "zh"), stem_suffix=" bi")
    s = _start(db_session, org, actor)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    ans = db_session.query(PracticeAnswer).filter_by(session_id=s.id).one()
    assert ans.question_snapshot["question_id"] == str(q.id)
    assert ans.is_correct is True
    assert ans.user_answer == {"selected": [0]}
    # canonical answer key frozen on options_snapshot
    assert [o["order_index"] for o in ans.options_snapshot] == [0, 1]
    assert [o["is_correct"] for o in ans.options_snapshot] == [True, False]


def test_answer_snapshot_records_mode_and_translations(db_session):
    """The frozen snapshot records the delivered language_mode + all translations."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor, langs=("en", "zh"), stem_suffix=" bi")
    s = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id,
        payload=SessionCreateIn(count=1, language_mode="bilingual", order_mode="sequential"),
    )
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    ans = db_session.query(PracticeAnswer).filter_by(session_id=s.id).one()
    snap = ans.question_snapshot
    assert snap["language_mode"] == "bilingual"
    assert set(snap["translations"].keys()) == {"en", "zh"}
    assert snap["translations"]["en"]["stem"] == "en stem bi"
    assert snap["translations"]["zh"]["stem"] == "中 stem bi"
    # each frozen translation carries its localized options
    assert snap["translations"]["en"]["options"][0]["content"] == "A"
    assert snap["translations"]["zh"]["options"][0]["content"] == "甲"


def test_re_answer_refused(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor)
    s = _start(db_session, org, actor)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    with pytest.raises(svc.ConflictError):
        svc.submit_answer(
            db_session, session_id=s.id, user_id=actor.id,
            payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
        )


def test_pause_resume(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor)
    s = _start(db_session, org, actor)
    svc.pause_session(db_session, session_id=s.id, user_id=actor.id)
    assert db_session.get(PracticeSession, s.id).paused_at is not None
    with pytest.raises(svc.ConflictError):
        svc.submit_answer(
            db_session, session_id=s.id, user_id=actor.id,
            payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
        )
    svc.resume_session(db_session, session_id=s.id, user_id=actor.id)
    assert db_session.get(PracticeSession, s.id).paused_at is None
    r = svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    assert r.is_correct is True


# --- summary -----------------------------------------------------------------


def test_finish_summary(db_session):
    from app.models.question import QuestionMapping
    from app.models.taxonomy import ExamBlueprint, ExamDomain

    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = ExamBlueprint(version_label="v1", effective_date="2026-04-15",
                       min_items=100, max_items=150, duration_minutes=180,
                       passing_score=700, max_score=1000, is_current=False)
    db_session.add(bp)
    db_session.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=10)
    db_session.add(dom)
    db_session.flush()
    q1 = _question(db_session, org, actor, stem_suffix=" right")  # 0 correct
    q2 = _question(db_session, org, actor, stem_suffix=" wrong")  # 0 correct
    db_session.add(QuestionMapping(question_id=q1.id, domain_id=dom.id))
    db_session.add(QuestionMapping(question_id=q2.id, domain_id=dom.id))
    db_session.flush()
    s = _start(db_session, org, actor, count=2)
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[0], started_at=datetime.now(timezone.utc)),
    )
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=1, selected=[1], started_at=datetime.now(timezone.utc)),
    )
    summary = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert summary.total_questions == 2
    assert summary.answered_count == 2
    assert summary.correct_count == 1
    assert summary.accuracy == 0.5
    assert len(summary.domains) == 1
    assert summary.domains[0].answered == 2
    assert summary.domains[0].correct == 1
    assert len(summary.wrong_questions) == 1
    assert summary.wrong_questions[0].question_id == q2.id
    assert db_session.get(PracticeSession, s.id).status == PracticeSessionStatus.completed


def test_summary_wrong_question_stem_is_bilingual(db_session):
    """Wrong-question stems in the summary are Localized {en,zh} from the snapshot."""
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor, langs=("en", "zh"), stem_suffix=" bi")
    s = _start(db_session, org, actor)
    # answer incorrectly to produce a wrong question
    svc.submit_answer(
        db_session, session_id=s.id, user_id=actor.id,
        payload=AnswerIn(position=0, selected=[1], started_at=datetime.now(timezone.utc)),
    )
    summary = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert len(summary.wrong_questions) == 1
    wq = summary.wrong_questions[0]
    assert wq.stem.model_dump() == {"en": "en stem bi", "zh": "中 stem bi"}
    assert wq.selected_indexes == [1]
    assert wq.correct_indexes == [0]


def test_finish_idempotent(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    _question(db_session, org, actor)
    s = _start(db_session, org, actor)
    a = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    b = svc.finish_session(db_session, session_id=s.id, user_id=actor.id)
    assert a.correct_count == b.correct_count


def test_other_user_session_not_found(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    intruder = _actor(db_session, org, email="other@example.com")
    _question(db_session, org, actor)
    s = _start(db_session, org, actor)
    with pytest.raises(svc.NotFound):
        svc.finish_session(db_session, session_id=s.id, user_id=intruder.id)


# --- per-user question state -------------------------------------------------


def test_set_question_state_upsert(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    q = _question(db_session, org, actor)
    svc.set_question_state(
        db_session, user_id=actor.id, org_id=org.id, question_id=q.id,
        payload=QuestionStateIn(is_bookmarked=True, note="hard"),
    )
    svc.set_question_state(
        db_session, user_id=actor.id, org_id=org.id, question_id=q.id,
        payload=QuestionStateIn(is_flagged_review=True),
    )
    state = db_session.query(UserQuestionState).filter_by(
        user_id=actor.id, question_id=q.id
    ).one()
    assert state.is_bookmarked is True
    assert state.is_flagged_review is True
    assert state.note == "hard"


def test_set_question_state_wrong_tenant_not_found(db_session):
    org = _org(db_session)
    other_org = _org(db_session, slug="o2")
    actor = _actor(db_session, org)
    q = _question(db_session, org, actor)
    with pytest.raises(svc.NotFound):
        svc.set_question_state(
            db_session, user_id=actor.id, org_id=other_org.id, question_id=q.id,
            payload=QuestionStateIn(is_bookmarked=True),
        )


def test_set_question_state_persists_error_type(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    q = _question(db_session, org, actor)
    state = svc.set_question_state(
        db_session, user_id=actor.id, org_id=org.id, question_id=q.id,
        payload=QuestionStateIn(error_type=ErrorType.concept_unclear),
    )
    assert state.error_type == ErrorType.concept_unclear
    # re-fetch from DB to confirm the value was persisted, not just in-memory
    db_session.flush()
    fresh = db_session.get(UserQuestionState, state.id)
    assert fresh.error_type == ErrorType.concept_unclear


def test_set_question_state_error_type_none_then_update(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    q = _question(db_session, org, actor)
    # Omitting error_type leaves it None on the initial upsert.
    state = svc.set_question_state(
        db_session, user_id=actor.id, org_id=org.id, question_id=q.id,
        payload=QuestionStateIn(is_bookmarked=True),
    )
    assert state.error_type is None
    # A second call supplying error_type updates the existing row.
    updated = svc.set_question_state(
        db_session, user_id=actor.id, org_id=org.id, question_id=q.id,
        payload=QuestionStateIn(error_type=ErrorType.misread_stem),
    )
    assert updated.id == state.id
    assert updated.error_type == ErrorType.misread_stem
