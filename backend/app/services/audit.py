"""Audit logging helper (NFR-DATA-05 / FR-ADMIN-06).

Writes a single AuditLog row. The session is NOT committed here; callers control
the transaction. Sub-projects call this from real actions (B/C onward).
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.admin import AuditLog
from app.models.enums import AuditAction


def log_audit(
    session: Session,
    *,
    action: AuditAction,
    actor_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        organization_id=organization_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address,
    )
    session.add(entry)
    session.flush()
    return entry
