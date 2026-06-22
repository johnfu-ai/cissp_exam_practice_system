"""Service-layer tests for taxonomy admin (sub-project D)."""

import pytest

from app.models.auth import Organization, User
from app.models.enums import OrgKind
from app.schemas.taxonomy import (
    BlueprintIn,
    BlueprintUpdateIn,
    BookIn,
    ChapterIn,
    DomainIn,
    KnowledgePointIn,
    BindingIn,
    TagIn,
)
from app.services import taxonomy_admin as svc


def _org(db_session, slug="t"):
    org = Organization(name="T", slug=slug, kind=OrgKind.personal)
    db_session.add(org)
    db_session.flush()
    return org


def _actor(db_session, org, email="admin@example.com"):
    user = User(
        email=email,
        password_hash="x",
        display_name="A",
        default_organization_id=org.id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _bp_payload(**kw):
    base = dict(
        version_label="2026-04-15",
        effective_date="2026-04-15",
        min_items=100,
        max_items=150,
        duration_minutes=180,
        passing_score=700,
        max_score=1000,
    )
    base.update(kw)
    return BlueprintIn(**base)


# --- ExamBlueprint ---


def test_create_blueprint_validates_bounds(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    with pytest.raises(svc.ValidationError):
        svc.create_blueprint(
            db_session,
            actor_id=actor.id,
            payload=_bp_payload(min_items=200, max_items=100),
        )


def test_create_blueprint(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    assert bp.id is not None
    assert bp.is_current is False
    assert bp.version_label == "2026-04-15"


def test_set_current_flips_others(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    a = svc.create_blueprint(
        db_session, actor_id=actor.id, payload=_bp_payload(version_label="a")
    )
    b = svc.create_blueprint(
        db_session, actor_id=actor.id, payload=_bp_payload(version_label="b")
    )
    svc.set_current_blueprint(db_session, blueprint_id=a.id, actor_id=actor.id)
    assert svc.get_blueprint(db_session, a.id).is_current is True
    assert svc.get_blueprint(db_session, b.id).is_current is False
    svc.set_current_blueprint(db_session, blueprint_id=b.id, actor_id=actor.id)
    assert svc.get_blueprint(db_session, a.id).is_current is False
    assert svc.get_blueprint(db_session, b.id).is_current is True


def test_update_blueprint_ignores_is_current(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    svc.set_current_blueprint(db_session, blueprint_id=bp.id, actor_id=actor.id)
    updated = svc.update_blueprint(
        db_session,
        blueprint_id=bp.id,
        actor_id=actor.id,
        payload=BlueprintUpdateIn(max_items=160),
    )
    assert updated.max_items == 160
    assert updated.is_current is True  # unchanged by update


def test_delete_current_blueprint_refused(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    svc.set_current_blueprint(db_session, blueprint_id=bp.id, actor_id=actor.id)
    with pytest.raises(svc.ConflictError):
        svc.delete_blueprint(db_session, blueprint_id=bp.id, actor_id=actor.id)


def test_delete_blueprint_with_mapped_questions_refused(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    domain = svc.create_domain(
        db_session,
        blueprint_id=bp.id,
        actor_id=actor.id,
        payload=DomainIn(number=1, name="D1", weight_pct=10),
    )
    from app.models.enums import QuestionType
    from app.models.question import Question, QuestionMapping

    q = Question(
        organization_id=org.id,
        question_type=QuestionType.single_choice,
        stem="x",
        created_by_id=actor.id,
    )
    db_session.add(q)
    db_session.flush()
    db_session.add(QuestionMapping(question_id=q.id, domain_id=domain.id))
    db_session.flush()
    with pytest.raises(svc.ConflictError):
        svc.delete_blueprint(db_session, blueprint_id=bp.id, actor_id=actor.id)


# --- ExamDomain ---


def test_create_domain_validates_weight(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    with pytest.raises(svc.ValidationError):
        svc.create_domain(
            db_session,
            blueprint_id=bp.id,
            actor_id=actor.id,
            payload=DomainIn(number=1, name="D1", weight_pct=200),
        )


def test_create_domain(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    d = svc.create_domain(
        db_session,
        blueprint_id=bp.id,
        actor_id=actor.id,
        payload=DomainIn(number=1, name="D1", weight_pct=12),
    )
    assert d.blueprint_id == bp.id
    assert d.weight_pct == 12


def test_create_domain_duplicate_number_refused(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    svc.create_domain(
        db_session,
        blueprint_id=bp.id,
        actor_id=actor.id,
        payload=DomainIn(number=1, name="D1", weight_pct=10),
    )
    with pytest.raises(svc.ConflictError):
        svc.create_domain(
            db_session,
            blueprint_id=bp.id,
            actor_id=actor.id,
            payload=DomainIn(number=1, name="D2", weight_pct=10),
        )


def test_delete_domain_with_mapped_questions_refused(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    domain = svc.create_domain(
        db_session,
        blueprint_id=bp.id,
        actor_id=actor.id,
        payload=DomainIn(number=1, name="D1", weight_pct=10),
    )
    from app.models.enums import QuestionType
    from app.models.question import Question, QuestionMapping

    q = Question(
        organization_id=org.id,
        question_type=QuestionType.single_choice,
        stem="x",
        created_by_id=actor.id,
    )
    db_session.add(q)
    db_session.flush()
    db_session.add(QuestionMapping(question_id=q.id, domain_id=domain.id))
    db_session.flush()
    with pytest.raises(svc.ConflictError):
        svc.delete_domain(
            db_session,
            blueprint_id=bp.id,
            domain_id=domain.id,
            actor_id=actor.id,
        )


def test_delete_domain_ok(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp = svc.create_blueprint(db_session, actor_id=actor.id, payload=_bp_payload())
    domain = svc.create_domain(
        db_session,
        blueprint_id=bp.id,
        actor_id=actor.id,
        payload=DomainIn(number=1, name="D1", weight_pct=10),
    )
    svc.delete_domain(
        db_session, blueprint_id=bp.id, domain_id=domain.id, actor_id=actor.id
    )
    assert len(svc.list_domains_for_blueprint(db_session, bp.id)) == 0


# --- Book + Chapter (tenant-scoped) ---


def test_create_book(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    book = svc.create_book(
        db_session, org_id=org.id, actor_id=actor.id, payload=BookIn(title="OSG")
    )
    assert book.organization_id == org.id
    assert book.title == "OSG"


def test_create_book_empty_title(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    with pytest.raises(svc.ValidationError):
        svc.create_book(
            db_session,
            org_id=org.id,
            actor_id=actor.id,
            payload=BookIn(title="  "),
        )


def test_get_book_tenant_isolation(db_session):
    org = _org(db_session, slug="t1")
    actor = _actor(db_session, org)
    book = svc.create_book(
        db_session, org_id=org.id, actor_id=actor.id, payload=BookIn(title="OSG")
    )
    other_org = _org(db_session, slug="t2")
    with pytest.raises(svc.NotFound):
        svc.get_book(db_session, book_id=book.id, org_id=other_org.id)


def test_delete_book_with_questions_refused(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    book = svc.create_book(
        db_session, org_id=org.id, actor_id=actor.id, payload=BookIn(title="B")
    )
    ch = svc.create_chapter(
        db_session,
        book_id=book.id,
        org_id=org.id,
        actor_id=actor.id,
        payload=ChapterIn(order_index=0, title="C1"),
    )
    from app.models.enums import QuestionType
    from app.models.question import Question, QuestionMapping

    q = Question(
        organization_id=org.id,
        question_type=QuestionType.single_choice,
        stem="x",
        created_by_id=actor.id,
    )
    db_session.add(q)
    db_session.flush()
    db_session.add(QuestionMapping(question_id=q.id, chapter_id=ch.id))
    db_session.flush()
    with pytest.raises(svc.ConflictError):
        svc.delete_book(db_session, book_id=book.id, org_id=org.id, actor_id=actor.id)


def test_create_chapter(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    book = svc.create_book(
        db_session, org_id=org.id, actor_id=actor.id, payload=BookIn(title="B")
    )
    ch = svc.create_chapter(
        db_session,
        book_id=book.id,
        org_id=org.id,
        actor_id=actor.id,
        payload=ChapterIn(order_index=1, title="C1"),
    )
    assert ch.book_id == book.id
    assert ch.order_index == 1


def test_delete_chapter_with_questions_refused(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    book = svc.create_book(
        db_session, org_id=org.id, actor_id=actor.id, payload=BookIn(title="B")
    )
    ch = svc.create_chapter(
        db_session,
        book_id=book.id,
        org_id=org.id,
        actor_id=actor.id,
        payload=ChapterIn(order_index=0, title="C1"),
    )
    from app.models.enums import QuestionType
    from app.models.question import Question, QuestionMapping

    q = Question(
        organization_id=org.id,
        question_type=QuestionType.single_choice,
        stem="x",
        created_by_id=actor.id,
    )
    db_session.add(q)
    db_session.flush()
    db_session.add(QuestionMapping(question_id=q.id, chapter_id=ch.id))
    db_session.flush()
    with pytest.raises(svc.ConflictError):
        svc.delete_chapter(
            db_session,
            book_id=book.id,
            chapter_id=ch.id,
            org_id=org.id,
            actor_id=actor.id,
        )
