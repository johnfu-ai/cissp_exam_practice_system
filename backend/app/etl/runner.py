"""ETL Runner: orchestrate extract -> transform -> load across preview/commit.

Owns the session lifecycle and writes EtlRun/ImportJob. One bilingual
CleanedQuestion is produced per raw record (no per-language fan-out).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.etl.extract import DatasetReader
from app.etl.load import apply_dry_run, apply_load
from app.etl.transform import transform, validate
from app.models.enums import AuditAction, EtlRunPhase, ImportStatus, LicenseStatus
from app.models.etl import EtlDataset, EtlRun
from app.models.question import ImportJob
from app.services.audit import log_audit


class EtlDriftError(Exception):
    """Dataset files changed between preview and commit."""


def _build_cleaned(raws, pending_ids):
    """Transform each raw into one bilingual CleanedQuestion (no language fan-out)."""
    cleaned = []
    errors = []
    for raw in raws:
        issues = validate(raw)
        if issues:
            errors.append({
                "external_id": raw.id,
                "language": None,
                "reason": "validation: " + "; ".join(issues),
            })
            continue
        cleaned.append(transform(raw, pending_ids))
    return cleaned, errors


def run_preview(session: Session, org_id: uuid.UUID, dataset: EtlDataset, initiated_by_id=None) -> EtlRun:
    job = ImportJob(
        organization_id=org_id,
        format=dataset.format,
        source=dataset.source_path,
        license_status=LicenseStatus.unconfirmed,
        status=ImportStatus.previewing,
        initiated_by_id=initiated_by_id,
    )
    session.add(job)
    session.flush()

    run = EtlRun(
        organization_id=org_id,
        dataset_id=dataset.id,
        import_job_id=job.id,
        phase=EtlRunPhase.preview,
    )
    session.add(run)
    session.flush()

    raws, extract_errors, content_hash = DatasetReader(dataset.source_path).read()
    pending_ids = set()  # translate_queue.json empty for osg10; read from manifest if present
    cleaned, transform_errors = _build_cleaned(raws, pending_ids)

    summary = apply_dry_run(session, org_id, dataset.slug, cleaned)
    all_errors = (
        [{"external_id": e.external_id, "language": None, "reason": e.reason} for e in extract_errors]
        + transform_errors
        + summary.errors
    )

    preview_summary = {
        "would_create": summary.would_create,
        "would_update": summary.would_update,
        "unchanged": summary.unchanged,
        "duplicates": summary.duplicates,
        "by_type": summary.by_type,
        "by_language": summary.by_language,
        "errors": all_errors,
        "conflicts": summary.conflicts,
        "content_hash": content_hash,
    }
    run.preview_summary = preview_summary
    job.total_rows = len(cleaned)
    job.error_count = len(all_errors)
    session.flush()
    return run


def run_commit(session: Session, org_id: uuid.UUID, run_id: uuid.UUID) -> EtlRun:
    run = session.get(EtlRun, run_id)
    if run is None or run.organization_id != org_id:
        raise LookupError(f"run {run_id} not found")
    if run.phase != EtlRunPhase.preview:
        raise ValueError(f"run {run_id} not in preview phase")
    dataset = session.get(EtlDataset, run.dataset_id)

    raws, extract_errors, content_hash = DatasetReader(dataset.source_path).read()
    if content_hash != run.preview_summary.get("content_hash"):
        raise EtlDriftError("dataset changed since preview; re-preview required")

    pending_ids = set()
    cleaned, transform_errors = _build_cleaned(raws, pending_ids)
    load_result = apply_load(session, org_id, dataset.slug, run.import_job_id, cleaned)

    run.phase = EtlRunPhase.committed
    run.committed_at = datetime.now(timezone.utc)

    job = session.get(ImportJob, run.import_job_id)
    job.status = ImportStatus.completed if not load_result.errors else ImportStatus.partial
    job.total_rows = len(cleaned)
    job.success_count = load_result.created
    job.error_count = len(load_result.errors) + len(transform_errors)
    job.error_report = {
        "errors": load_result.errors + transform_errors,
        "conflicts": load_result.conflicts,
    }

    log_audit(
        session,
        action=AuditAction.import_action,
        actor_id=None,
        organization_id=org_id,
        entity_type="etl_run",
        entity_id=str(run.id),
        details={"dataset": dataset.slug, "created": load_result.created,
                 "updated": load_result.updated, "unchanged": load_result.unchanged,
                 "duplicates": load_result.duplicates},
    )
    session.flush()
    return run


def run_rollback(session: Session, run_id: uuid.UUID, *, org_id: uuid.UUID) -> EtlRun:
    run = session.get(EtlRun, run_id)
    if run is None or run.organization_id != org_id:
        raise LookupError(f"run {run_id} not found")
    if run.phase != EtlRunPhase.preview:
        raise ValueError(f"run {run_id} not in preview phase")
    run.phase = EtlRunPhase.rolled_back
    job = session.get(ImportJob, run.import_job_id)
    job.status = ImportStatus.failed
    session.flush()
    return run
