"""User preference service (language_mode).

Reads/updates ``User.language_mode``. ``PreferencesIn.language_mode`` is a
``Literal["en","zh","bilingual"]`` so FastAPI returns 422 for invalid values
at the schema layer before the service is reached; the explicit
``LANGUAGE_MODES`` check here guards direct (non-HTTP) callers too.
"""

from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import LANGUAGE_MODES, AuditAction
from app.services.audit import log_audit


def get_preferences(session: Session, user: User):
    from app.schemas.auth import PreferencesOut

    return PreferencesOut(language_mode=getattr(user, "language_mode", "en") or "en")


def set_preferences(session: Session, user: User, language_mode: str):
    from app.schemas.auth import PreferencesOut

    if language_mode not in LANGUAGE_MODES:
        raise ValueError("invalid language_mode")
    user.language_mode = language_mode
    session.flush()
    log_audit(
        session,
        action=AuditAction.config_change,
        actor_id=user.id,
        organization_id=user.default_organization_id,
        entity_type="user",
        entity_id=str(user.id),
        details={"language_mode": language_mode},
    )
    return PreferencesOut(language_mode=language_mode)
