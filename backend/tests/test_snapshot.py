"""Snapshot test for the bilingual, translations-based snapshot producer.

The shared `make_question_with_translations` fixture is created in Task 4's
test module; it does not exist yet. Per the task brief we build the
Question + QuestionOption + QuestionTranslation rows inline here (mirroring
`tests/test_models.py`) and call `snapshot_question` with its new signature:
`snapshot_question(question, translations, options, *, language_mode=None)`.
"""
from app.models.auth import Organization
from app.models.enums import OrgKind, QuestionStatus, QuestionType, TextFormat
from app.models.question import Question, QuestionOption, QuestionTranslation
from app.services.snapshot import snapshot_question


def _make_question_with_translations(
    db_session,
    *,
    en_stem,
    zh_stem,
    options_en,
    options_zh,
    rationale_en,
    rationale_zh,
):
    """Build a Question + canonical options + en/zh translations inline.

    Returns (question, options, translations) where `options` is the canonical
    QuestionOption list (order_index 0..N-1) and `translations` is the
    QuestionTranslation list ([en, zh]).
    """
    org = Organization(name="Acme", slug="acme-snap", kind=OrgKind.institution)
    db_session.add(org)
    db_session.flush()

    q = Question(
        organization_id=org.id,
        question_type=QuestionType.single_choice,
        status=QuestionStatus.draft,
        available_languages=["en", "zh"],
        version=1,
    )
    db_session.add(q)
    db_session.flush()

    # Canonical options: order_index 0 incorrect, 1 correct (mirrors the
    # historical snapshot test's "4 is correct" shape).
    options = [
        QuestionOption(question_id=q.id, order_index=0, is_correct=False),
        QuestionOption(question_id=q.id, order_index=1, is_correct=True),
    ]
    db_session.add_all(options)
    db_session.flush()

    def _trans(language, stem, option_contents, rationale):
        return QuestionTranslation(
            question_id=q.id,
            language=language,
            stem=stem,
            stem_format=TextFormat.markdown,
            correct_answer_rationale=rationale,
            key_point_summary=None,
            further_reading=None,
            options=[
                {
                    "order_index": i,
                    "content": text,
                    "content_format": TextFormat.markdown.value,
                    "explanation": None,
                }
                for i, text in enumerate(option_contents)
            ],
        )

    translations = [
        _trans("en", en_stem, options_en, rationale_en),
        _trans("zh", zh_stem, options_zh, rationale_zh),
    ]
    db_session.add_all(translations)
    db_session.flush()
    return q, options, translations


def test_snapshot_freezes_all_translations_and_mode(db_session):
    q, options, translations = _make_question_with_translations(
        db_session,
        en_stem="en stem",
        zh_stem="中文题干",
        options_en=["A", "B"],
        options_zh=["甲", "乙"],
        rationale_en="en why",
        rationale_zh="中文解析",
    )
    snap = snapshot_question(q, translations, options, language_mode="zh")
    assert snap["language_mode"] == "zh"
    assert snap["available_languages"] == ["en", "zh"]
    assert snap["translations"]["en"]["stem"] == "en stem"
    assert snap["translations"]["zh"]["stem"] == "中文题干"
    assert snap["translations"]["zh"]["options"][0]["content"] == "甲"
    # canonical correctness frozen
    assert [o["is_correct"] for o in snap["options"]] == [o.is_correct for o in options]
