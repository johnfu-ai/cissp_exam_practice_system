"""Shared i18n helpers for the practice and exam services.

Language-mode candidate filtering and bilingual delivery rendering live here so
``app.services.practice`` and ``app.services.exam`` share one implementation
without creating a practice↔exam import cycle.

A *language mode* is one of ``en`` / ``zh`` / ``bilingual``. It governs:
  * which questions are eligible for a session (``language_filter``), and
  * how a delivered question/answer is rendered (``localized_stem``,
    ``delivery_options``) — always as a ``Localized`` ``{en, zh}`` pair so a
    single response can serve any mode.

These helpers are pure query/render utilities; they do not mutate state.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.question import Question, QuestionOption, QuestionTranslation


def language_filter(mode: str):
    """Return a SQLAlchemy predicate on ``Question.available_languages`` for a mode.

    * ``en``        — question has an ``en`` translation
    * ``zh``        — question has a ``zh`` translation
    * ``bilingual`` — question has both ``en`` and ``zh``
    """
    if mode == "en":
        return Question.available_languages.any("en")
    if mode == "zh":
        return Question.available_languages.any("zh")
    # bilingual: both languages must be present
    return Question.available_languages.any("en") & Question.available_languages.any("zh")


def resolve_mode(session: Session, user_id, payload_mode) -> str:
    """Resolve the effective language mode.

    An explicit payload mode wins; otherwise the user's ``language_mode``
    preference is used; otherwise ``en``.
    """
    if payload_mode:
        return payload_mode
    u = session.get(User, user_id)
    return (u.language_mode if u and u.language_mode else "en")


def translations_for(session: Session, question_id) -> list[QuestionTranslation]:
    """Return all translation rows for a question (unordered)."""
    return list(
        session.execute(
            select(QuestionTranslation).where(
                QuestionTranslation.question_id == question_id
            )
        ).scalars().all()
    )


def localized_stem(translations: list[QuestionTranslation]) -> dict:
    """Render a ``{en, zh}`` stem view across the present translations."""
    return {
        "en": next((t.stem for t in translations if t.language == "en"), None),
        "zh": next((t.stem for t in translations if t.language == "zh"), None),
    }


def delivery_options(
    options: list[QuestionOption],
    translations: list[QuestionTranslation],
) -> list[dict]:
    """Render localized per-option cells, 1:1 by ``order_index``.

    Each cell is ``{id, order_index, content{en,zh}, content_format{en,zh}}``
    matching the ``OptionDelivery`` schema. Content is pulled from each
    translation's ``options`` JSONB by ``order_index``; missing languages stay
    ``None``.
    """
    out = []
    for o in sorted(options, key=lambda x: x.order_index):
        cell = {
            "id": str(o.id),
            "order_index": o.order_index,
            "content": {"en": None, "zh": None},
            "content_format": {"en": None, "zh": None},
        }
        for t in translations:
            to = next(
                (
                    x
                    for x in (t.options or [])
                    if x.get("order_index") == o.order_index
                ),
                None,
            )
            if to:
                cell["content"][t.language] = to.get("content")
                cell["content_format"][t.language] = to.get("content_format")
        out.append(cell)
    return out
