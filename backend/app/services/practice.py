"""Practice session service (sub-project E).

Owns session creation, question delivery, answer judging (from snapshot),
pause/resume, finish/summary, and per-user question state.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.queries import not_deleted
from app.models.enums import (
    AuditAction,
    MasteryLevel,
    PracticeSessionStatus,
    QuestionStatus,
)
from app.models.practice import (
    PracticeAnswer,
    PracticeSession,
    UserQuestionState,
)
from app.models.question import (
    Explanation,
    Question,
    QuestionMapping,
    QuestionOption,
)
from app.schemas.practice import (
    AnswerIn,
    AnswerResultOut,
    QuestionStateIn,
    SessionCreateIn,
    SessionSummaryOut,
)
from app.services.audit import log_audit
from app.services.snapshot import snapshot_question


class ValidationError(ValueError):
    pass


class NotFound(LookupError):
    pass


class ConflictError(ValueError):
    pass


def create_session(
    session: Session, *, org_id, actor_id, payload: SessionCreateIn
) -> PracticeSession:
    raise NotImplementedError
