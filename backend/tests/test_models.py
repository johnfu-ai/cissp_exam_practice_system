import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKey,
)
from app.db.queries import not_deleted
from app.models.auth import Organization, Role
from app.models.enums import OrgKind, QuestionType, RoleName
from app.models.question import Question, QuestionOption
from app.models.taxonomy import ExamBlueprint, ExamDomain, KnowledgePoint


class _Widget(UUIDPrimaryKey, TimestampMixin, SoftDeleteMixin, Base):
    """Throwaway table created once per session by the engine fixture's
    create_all. Per-test inserts are rolled back by the db_session fixture, so
    no per-test create/drop is needed (which would deadlock against the open
    session transaction)."""

    __tablename__ = "_test_widgets"
    name: Mapped[str] = mapped_column(nullable=False)


def test_timestamps_set_on_insert(db_session):
    w = _Widget(name="alpha")
    db_session.add(w)
    db_session.flush()
    assert w.created_at is not None
    assert w.updated_at is not None
    assert w.id is not None and isinstance(w.id, uuid.UUID)


def test_soft_delete_default_none(db_session):
    w = _Widget(name="beta")
    db_session.add(w)
    db_session.flush()
    assert w.deleted_at is None


def test_not_deleted_filter_excludes_soft_deleted(db_session):
    live = _Widget(name="live")
    dead = _Widget(name="dead")
    dead.deleted_at = datetime.now()
    db_session.add_all([live, dead])
    db_session.flush()

    rows = db_session.execute(select(_Widget).where(not_deleted(_Widget))).scalars().all()
    names = {r.name for r in rows}
    assert names == {"live"}


def test_uuid_primary_key_default(db_session):
    w = _Widget(name="gamma")
    db_session.add(w)
    db_session.flush()
    db_session.refresh(w)
    assert isinstance(w.id, uuid.UUID)


def test_organization_insert(db_session):
    org = Organization(name="Personal", slug="personal", kind=OrgKind.personal)
    db_session.add(org)
    db_session.flush()
    assert org.id is not None
    assert org.status.value == "active"


def test_user_email_column_exists(engine):
    from sqlalchemy import inspect

    cols = {c["name"] for c in inspect(engine).get_columns("users")}
    assert "email" in cols


def test_role_unique_name(db_session):
    r = Role(name=RoleName.system_admin, description="root")
    db_session.add(r)
    db_session.flush()
    assert r.id is not None


def test_blueprint_and_domain(db_session):
    bp = ExamBlueprint(
        version_label="2024-04-15",
        effective_date=date(2024, 4, 15),
        min_items=100,
        max_items=150,
        duration_minutes=180,
        passing_score=700,
        max_score=1000,
        is_current=True,
    )
    db_session.add(bp)
    db_session.flush()

    d1 = ExamDomain(
        blueprint_id=bp.id, number=1, name="Security and Risk Management", weight_pct=16
    )
    db_session.add(d1)
    db_session.flush()
    assert d1.id is not None
    assert d1.weight_pct == 16


def test_knowledge_point_self_reference(db_session):
    parent = KnowledgePoint(name="Cryptography")
    db_session.add(parent)
    db_session.flush()
    child = KnowledgePoint(name="Symmetric", parent_id=parent.id)
    db_session.add(child)
    db_session.flush()
    assert child.parent_id == parent.id


def _make_org(db_session):
    org = Organization(name="Acme", slug="acme", kind=OrgKind.institution)
    db_session.add(org)
    db_session.flush()
    return org


def test_question_tenant_scoped_and_soft_delete(db_session):
    org = _make_org(db_session)
    q = Question(
        organization_id=org.id,
        question_type=QuestionType.single_choice,
        stem="What is CIA?",
        stem_format="markdown",
    )
    db_session.add(q)
    db_session.flush()
    assert q.organization_id == org.id
    assert q.status.value == "draft"
    assert q.license_status.value == "unconfirmed"
    assert q.version == 1
    assert q.deleted_at is None
    assert q.created_by_id is None


def test_question_option(db_session):
    org = _make_org(db_session)
    q = Question(
        organization_id=org.id,
        question_type=QuestionType.multiple_choice,
        stem="Pick two",
    )
    db_session.add(q)
    db_session.flush()
    opt = QuestionOption(
        question_id=q.id, order_index=0, content="Option A", is_correct=True
    )
    db_session.add(opt)
    db_session.flush()
    assert opt.is_correct is True


def test_question_translation_model_columns(db_session):
    from app.models.enums import QuestionStatus, TextFormat
    from app.models.question import Question, QuestionOption, QuestionTranslation

    org = _make_org(db_session)
    q = Question(
        organization_id=org.id,
        question_type=QuestionType.single_choice,
        status=QuestionStatus.draft,
        available_languages=["en", "zh"],
    )
    db_session.add(q)
    db_session.flush()
    db_session.add(QuestionOption(question_id=q.id, order_index=0, is_correct=True))
    db_session.add(QuestionOption(question_id=q.id, order_index=1, is_correct=False))
    t = QuestionTranslation(
        question_id=q.id,
        language="en",
        stem="Which principle?",
        stem_format=TextFormat.markdown,
        correct_answer_rationale="Because.",
        options=[
            {"order_index": 0, "content": "A", "content_format": "markdown", "explanation": None},
            {"order_index": 1, "content": "B", "content_format": "markdown", "explanation": None},
        ],
    )
    db_session.add(t)
    db_session.flush()
    assert q.available_languages == ["en", "zh"]
    assert not hasattr(q, "stem")
    assert not hasattr(QuestionOption, "content") or "content" not in QuestionOption.__table__.columns
    assert t.options[0]["content"] == "A"


def test_user_has_language_mode(db_session):
    from app.models.auth import User

    u = User(email="x@y.com", language_mode="bilingual")
    db_session.add(u)
    db_session.flush()
    assert u.language_mode == "bilingual"
