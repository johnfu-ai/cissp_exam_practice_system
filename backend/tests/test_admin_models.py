from datetime import date

from app.models.admin import CatParamsVersion
from app.models.auth import Class, ClassMembership, Organization, User


def test_cat_params_version_persists(db_session):
    org = Organization(name="Org", slug="org", kind="personal", status="active")
    db_session.add(org); db_session.flush()
    cpv = CatParamsVersion(
        version_label="v1", effective_date=date(2026, 1, 1),
        is_current=True, params={"k0": 0.5, "decay": 0.1, "base_se": 1.0, "early_stop_enabled": True},
    )
    db_session.add(cpv); db_session.flush()
    got = db_session.get(CatParamsVersion, cpv.id)
    assert got.params["k0"] == 0.5
    assert got.is_current is True


def test_class_and_membership_persist(db_session):
    org = Organization(name="Org", slug="org2", kind="personal", status="active")
    db_session.add(org); db_session.flush()
    u = User(email="c@example.com", status="active", default_organization_id=org.id)
    db_session.add(u); db_session.flush()
    cls = Class(organization_id=org.id, name="Section A", description="d", instructor_id=u.id)
    db_session.add(cls); db_session.flush()
    m = ClassMembership(class_id=cls.id, user_id=u.id)
    db_session.add(m); db_session.flush()
    assert db_session.get(Class, cls.id).name == "Section A"
    assert db_session.get(ClassMembership, m.id).user_id == u.id
