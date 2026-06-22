"""Fixed exam service (sub-project F).

Owns fixed-count exam session creation with domain-weighted auto-assembly
from the current ExamBlueprint, timed feedback-free delivery with lazy
auto-submit, revisable answer submission (judged from snapshot), finish +
report, unified post-exam review, and history/trend.
"""


class ValidationError(ValueError):
    pass


class NotFound(LookupError):
    pass


class ConflictError(ValueError):
    pass


def create_session(session, *, org_id, actor_id, payload):
    raise NotImplementedError


def get_question_at(session, *, session_id, position, user_id):
    raise NotImplementedError


def submit_answer(session, *, session_id, user_id, payload):
    raise NotImplementedError


def finish_session(session, *, session_id, user_id):
    raise NotImplementedError


def get_report(session, *, session_id, user_id):
    raise NotImplementedError


def get_review(session, *, session_id, user_id):
    raise NotImplementedError


def list_history(session, *, user_id):
    raise NotImplementedError
