from app.models.admin import AuditLog, SchemaMeta
from app.models.enums import AuditAction
from app.services.audit import log_audit


def test_log_audit_inserts_row(db_session):
    entry = log_audit(
        db_session,
        action=AuditAction.publish,
        entity_type="question",
        entity_id="abc-123",
        details={"from": "draft", "to": "published"},
    )
    db_session.flush()
    db_session.refresh(entry)
    assert entry.id is not None
    assert entry.action == AuditAction.publish
    assert entry.details["to"] == "published"
    assert entry.occurred_at is not None


def test_schema_meta_key_value(db_session):
    m = SchemaMeta(key="seed_version", value="1")
    db_session.add(m)
    db_session.flush()
    db_session.refresh(m)
    assert m.key == "seed_version"
    assert m.value == "1"
