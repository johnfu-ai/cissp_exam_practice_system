"""Snapshot producer for historical answer integrity (NFR-DATA-01).

Captures a frozen, minimal representation of a question and its options at
answer time so later edits never alter historical records. The blob lives in
JSONB and may evolve its internal shape without a migration.
"""

from typing import Any

from app.models.question import Question, QuestionOption


def snapshot_question(question: Question, options: list[QuestionOption]) -> dict[str, Any]:
    return {
        "question_id": str(question.id),
        "question_type": question.question_type.value,
        "stem": question.stem,
        "stem_format": question.stem_format.value,
        "difficulty": question.difficulty,
        "language": question.language,
        "version": question.version,
        "options": [
            {
                "order_index": o.order_index,
                "content": o.content,
                "content_format": o.content_format.value,
                "is_correct": o.is_correct,
            }
            for o in sorted(options, key=lambda o: o.order_index)
        ],
    }
