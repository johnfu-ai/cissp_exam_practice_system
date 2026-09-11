"""User preference service (language_mode + interface_language + goals).

Reads/updates ``User.language_mode`` (question content language:
en/zh/bilingual), ``User.interface_language`` (UI chrome language:
en/zh), and the FR-USER-06 learner goals (``exam_target_date`` /
``daily_goal_answers``). The ``Literal`` annotations on ``PreferencesIn``
make FastAPI return 422 for invalid values at the schema layer before the
service is reached; the explicit ``LANGUAGE_MODES`` / ``INTERFACE_LANGUAGES``
checks here guard direct (non-HTTP) callers too.
"""

from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import INTERFACE_LANGUAGES, LANGUAGE_MODES, AuditAction
from app.services.audit import log_audit


def get_preferences(session: Session, user: User):
    from app.schemas.auth import PreferencesOut

    return PreferencesOut(
        language_mode=getattr(user, "language_mode", "en") or "en",
        interface_language=getattr(user, "interface_language", "en") or "en",
        exam_target_date=getattr(user, "exam_target_date", None),
        daily_goal_answers=getattr(user, "daily_goal_answers", None),
    )


def set_preferences(
    session: Session,
    user: User,
    language_mode: str | None = None,
    interface_language: str | None = None,
    exam_target_date=...,  # ..., None, or a date — sentinel distinguishes
    daily_goal_answers=...,  #   "leave unchanged" from "clear to null"
):
    """Update whichever preferences are provided.

    Goal fields use ``...`` (ellipsis, the default) as "leave unchanged";
    passing ``None`` explicitly CLEARS the goal. The range check on
    ``daily_goal_answers`` (1..500) mirrors the schema-level constraint for
    direct callers.
    """
    from app.schemas.auth import PreferencesOut

    if language_mode is not None and language_mode not in LANGUAGE_MODES:
        raise ValueError("invalid language_mode")
    if interface_language is not None and interface_language not in INTERFACE_LANGUAGES:
        raise ValueError("invalid interface_language")
    if daily_goal_answers is not ... and daily_goal_answers is not None:
        if not isinstance(daily_goal_answers, int) or not (1 <= daily_goal_answers <= 500):
            raise ValueError("daily_goal_answers must be an int between 1 and 500")
    details: dict = {}
    if language_mode is not None:
        user.language_mode = language_mode
        details["language_mode"] = language_mode
    if interface_language is not None:
        user.interface_language = interface_language
        details["interface_language"] = interface_language
    if exam_target_date is not ...:
        user.exam_target_date = exam_target_date
        details["exam_target_date"] = str(exam_target_date)
    if daily_goal_answers is not ...:
        user.daily_goal_answers = daily_goal_answers
        details["daily_goal_answers"] = daily_goal_answers
    session.flush()
    log_audit(
        session,
        action=AuditAction.config_change,
        actor_id=user.id,
        organization_id=user.default_organization_id,
        entity_type="user",
        entity_id=str(user.id),
        details=details,
    )
    return PreferencesOut(
        language_mode=user.language_mode,
        interface_language=user.interface_language,
        exam_target_date=user.exam_target_date,
        daily_goal_answers=user.daily_goal_answers,
    )
