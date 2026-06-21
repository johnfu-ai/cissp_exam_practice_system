from app.models.auth import Organization, User
from app.models.enums import OrgKind, QuestionType, UserStatus
from app.models.practice import PracticeAnswer, PracticeSession
from app.models.question import Question, QuestionOption
from app.services.snapshot import snapshot_question


def test_snapshot_question_round_trips_through_jsonb(db_session):
    org = Organization(name="Acme", slug="acme", kind=OrgKind.institution)
    db_session.add(org)
    db_session.flush()

    q = Question(
        organization_id=org.id,
        question_type=QuestionType.single_choice,
        stem="What is 2+2?",
        difficulty=2,
        language="en",
        version=1,
    )
    db_session.add(q)
    db_session.flush()

    opts = [
        QuestionOption(question_id=q.id, order_index=0, content="3", is_correct=False),
        QuestionOption(question_id=q.id, order_index=1, content="4", is_correct=True),
    ]
    db_session.add_all(opts)
    db_session.flush()

    snap = snapshot_question(q, opts)
    assert snap["question_type"] == "single_choice"
    assert snap["stem"] == "What is 2+2?"
    assert len(snap["options"]) == 2
    assert snap["options"][0]["content"] == "3"
    assert snap["options"][1]["is_correct"] is True

    user = User(email="a@b.com", status=UserStatus.active, default_organization_id=org.id)
    db_session.add(user)
    db_session.flush()
    sess = PracticeSession(organization_id=org.id, user_id=user.id, total_questions=1)
    db_session.add(sess)
    db_session.flush()

    pa = PracticeAnswer(
        session_id=sess.id,
        user_id=user.id,
        question_id=q.id,
        question_snapshot=snap,
        options_snapshot=snap["options"],
        user_answer={"indices": [1]},
        is_correct=True,
    )
    db_session.add(pa)
    db_session.flush()
    db_session.refresh(pa)

    assert pa.question_snapshot["options"][1]["is_correct"] is True
    assert pa.options_snapshot[0]["content"] == "3"
