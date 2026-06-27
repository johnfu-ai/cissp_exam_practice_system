"""User preference service (language_mode + interface_language).

Reads/updates ``User.language_mode`` (question content language:
en/zh/bilingual) and ``User.interface_language`` (UI chrome language:
en/zh). The ``Literal`` annotations on ``PreferencesIn`` make FastAPI
return 422 for invalid values at the schema layer before the service is
reached; the explicit ``LANGUAGE_MODES`` / ``INTERFACE_LANGUAGES``
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
    )


def set_preferences(
    session: Session,
    user: User,
    language_mode: str | None = None,
    interface_language: str | None = None,
):
    from app.schemas.auth import PreferencesOut

    if language_mode is not None and language_mode not in LANGUAGE_MODES:
        raise ValueError("invalid language_mode")
    if interface_language is not None and interface_language not in INTERFACE_LANGUAGES:
        raise ValueError("invalid interface_language")
    details: dict = {}
    if language_mode is not None:
        user.language_mode = language_mode
        details["language_mode"] = language_mode
    if interface_language is not None:
        user.interface_language = interface_language
        details["interface_language"] = interface_language
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
    )
