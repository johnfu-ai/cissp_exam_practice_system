"""ETL HTTP API. Permission-gated via app.dependencies."""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_session
from app.dependencies import CurrentUser, require_permission
from app.etl.runner import run_commit, run_preview, run_rollback
from app.models.enums import ImportFormat
from app.models.etl import ChapterDomainMapping, EtlDataset, EtlRun

router = APIRouter(prefix="/api/etl", tags=["etl"])

_UPLOAD_EXTS = {".csv": ImportFormat.csv, ".xlsx": ImportFormat.xlsx, ".json": ImportFormat.json}


class CreateRunIn(BaseModel):
    dataset_slug: str


class MappingIn(BaseModel):
    dataset_slug: str
    chapter_number: int
    chapter_title: str
    domain_id: uuid.UUID | None = None


class PasteIn(BaseModel):
    markdown: str
    dataset_slug: str | None = None


@router.get("/datasets")
def list_datasets(session: Session = Depends(get_session),
                  _: CurrentUser = Depends(require_permission("question:import"))):
    rows = session.execute(select(EtlDataset)).scalars().all()
    return [{"id": str(d.id), "slug": d.slug, "name": d.name,
             "source_path": d.source_path, "total_questions": d.total_questions,
             "languages": d.languages} for d in rows]


@router.get("/datasets/{slug}")
def get_dataset(slug: str, session: Session = Depends(get_session),
                _: CurrentUser = Depends(require_permission("question:import"))):
    d = session.execute(select(EtlDataset).filter_by(slug=slug)).scalar_one_or_none()
    if d is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return {"id": str(d.id), "slug": d.slug, "name": d.name,
            "source_path": d.source_path, "total_questions": d.total_questions,
            "languages": d.languages}


@router.post("/runs")
def create_run(body: CreateRunIn, session: Session = Depends(get_session),
               current: CurrentUser = Depends(require_permission("question:import"))):
    ds = session.execute(select(EtlDataset).filter_by(slug=body.dataset_slug)).scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    run = run_preview(session, current.org_id, ds, initiated_by_id=current.user.id)
    session.commit()
    return {"run_id": str(run.id), "phase": run.phase.value, "preview_summary": run.preview_summary}


@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    dataset_slug: str = Form(...),
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:import")),
):
    """FR-IMP-01 / #35: upload a CSV/XLSX/JSON question file, materialize it as a
    dataset directory, and run a preview (extract+transform). Returns the same
    shape as ``POST /runs`` so the existing commit/rollback flow reuses verbatim.

    The file is written to ``<etl_upload_root>/<dataset_slug>/questions.<ext>``
    so ``DatasetReader`` auto-detects it and re-reads at commit time for drift
    detection (the same mechanism the JSONL path uses).
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _UPLOAD_EXTS:
        raise HTTPException(
            status_code=422,
            detail="unsupported file type; use .csv, .xlsx, or .json",
        )
    slug = (dataset_slug or "").strip()
    if not slug:
        raise HTTPException(status_code=422, detail="dataset_slug is required")

    target_dir = Path(settings.etl_upload_root) / slug
    target_dir.mkdir(parents=True, exist_ok=True)
    # Remove any prior upload of a different format for this slug so the
    # directory contains exactly one questions.* file (auto-detection picks it).
    for old in target_dir.glob("questions.*"):
        if old.suffix != ext:
            old.unlink()
    target = target_dir / f"questions{ext}"
    # Write to a sibling temp file first so a rejected oversized upload cannot
    # truncate an existing dataset on disk (NFR-SEC-08 / re-upload safety).
    tmp = target_dir / f".questions{ext}.{uuid.uuid4().hex}.partial"
    max_bytes = settings.max_upload_bytes
    written = 0
    try:
        with tmp.open("wb") as out:
            while True:
                chunk = file.file.read(64 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"upload exceeds max size of {max_bytes} bytes",
                    )
                out.write(chunk)
        tmp.replace(target)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    ds = session.execute(select(EtlDataset).filter_by(slug=slug)).scalar_one_or_none()
    if ds is None:
        ds = EtlDataset(
            organization_id=current.org_id,
            slug=slug,
            name=slug,
            source_path=str(target_dir),
            format=_UPLOAD_EXTS[ext],
            languages=["en"],
            total_questions=0,
        )
        session.add(ds)
    else:
        # A slug owned by another org looks the same as "not found" (no leak).
        if ds.organization_id != current.org_id:
            raise HTTPException(status_code=404, detail="dataset not found")
        ds.source_path = str(target_dir)
        ds.format = _UPLOAD_EXTS[ext]
    session.flush()

    run = run_preview(session, current.org_id, ds, initiated_by_id=current.user.id)
    summary = run.preview_summary or {}
    ds.total_questions = (
        summary.get("would_create", 0) + summary.get("would_update", 0) + summary.get("unchanged", 0)
    )
    session.commit()
    return {
        "run_id": str(run.id),
        "phase": run.phase.value,
        "preview_summary": run.preview_summary,
        "dataset_slug": slug,
    }


@router.post("/paste")
def paste_markdown(
    body: PasteIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:import")),
):
    """FR-IMP-02: interactive Markdown paste → materialize as questions.json → preview."""
    import json

    from app.etl.markdown_paste import markdown_content_hash, parse_markdown_paste

    md = (body.markdown or "").strip()
    if not md:
        raise HTTPException(status_code=422, detail="markdown is required")
    rows = parse_markdown_paste(md)
    if not rows:
        raise HTTPException(
            status_code=422,
            detail="no questions parsed; need stem + options A./B. … and optional Answer:/答案:",
        )
    # Drop internal helper keys before writing JSON for JsonExtractor.
    clean_rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    slug = (body.dataset_slug or "").strip() or f"paste-{markdown_content_hash(md)}"
    target_dir = Path(settings.etl_upload_root) / slug
    target_dir.mkdir(parents=True, exist_ok=True)
    for old in target_dir.glob("questions.*"):
        old.unlink()
    target = target_dir / "questions.json"
    target.write_text(json.dumps(clean_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    ds = session.execute(select(EtlDataset).filter_by(slug=slug)).scalar_one_or_none()
    if ds is None:
        ds = EtlDataset(
            organization_id=current.org_id,
            slug=slug,
            name=slug,
            source_path=str(target_dir),
            format=ImportFormat.json,
            languages=["en"],
            total_questions=0,
        )
        session.add(ds)
    else:
        if ds.organization_id != current.org_id:
            raise HTTPException(status_code=404, detail="dataset not found")
        ds.source_path = str(target_dir)
        ds.format = ImportFormat.json
    session.flush()

    run = run_preview(session, current.org_id, ds, initiated_by_id=current.user.id)
    summary = run.preview_summary or {}
    ds.total_questions = (
        summary.get("would_create", 0) + summary.get("would_update", 0) + summary.get("unchanged", 0)
    )
    session.commit()
    return {
        "run_id": str(run.id),
        "phase": run.phase.value,
        "preview_summary": run.preview_summary,
        "dataset_slug": slug,
    }


@router.get("/runs/{run_id}")
def get_run(run_id: uuid.UUID, session: Session = Depends(get_session),
            current: CurrentUser = Depends(require_permission("question:import"))):
    run = session.get(EtlRun, run_id)
    if run is None or run.organization_id != current.org_id:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": str(run.id), "phase": run.phase.value,
            "preview_summary": run.preview_summary, "committed_at": run.committed_at}


@router.post("/runs/{run_id}/commit")
def commit_run(run_id: uuid.UUID, session: Session = Depends(get_session),
               current: CurrentUser = Depends(require_permission("question:import"))):
    try:
        run = run_commit(session, current.org_id, run_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="run not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    session.commit()
    return {"run_id": str(run.id), "phase": run.phase.value}


@router.post("/runs/{run_id}/rollback")
def rollback_run(run_id: uuid.UUID, session: Session = Depends(get_session),
                 current: CurrentUser = Depends(require_permission("question:import"))):
    try:
        run = run_rollback(session, run_id, org_id=current.org_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="run not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    session.commit()
    return {"run_id": str(run.id), "phase": run.phase.value}


@router.get("/mappings")
def list_mappings(dataset_slug: str | None = None, session: Session = Depends(get_session),
                  _: CurrentUser = Depends(require_permission("admin:manage_taxonomy"))):
    stmt = select(ChapterDomainMapping)
    if dataset_slug:
        stmt = stmt.filter_by(dataset_slug=dataset_slug)
    rows = session.execute(stmt).scalars().all()
    return [{"id": str(m.id), "dataset_slug": m.dataset_slug,
             "chapter_number": m.chapter_number, "chapter_title": m.chapter_title,
             "domain_id": str(m.domain_id) if m.domain_id else None} for m in rows]


@router.post("/mappings")
def create_mapping(body: MappingIn, session: Session = Depends(get_session),
                   _: CurrentUser = Depends(require_permission("admin:manage_taxonomy"))):
    m = ChapterDomainMapping(dataset_slug=body.dataset_slug, chapter_number=body.chapter_number,
                             chapter_title=body.chapter_title, domain_id=body.domain_id)
    session.add(m)
    session.commit()
    return {"id": str(m.id), "dataset_slug": m.dataset_slug, "chapter_number": m.chapter_number}


@router.put("/mappings/{mapping_id}")
def update_mapping(mapping_id: uuid.UUID, body: MappingIn, session: Session = Depends(get_session),
                   _: CurrentUser = Depends(require_permission("admin:manage_taxonomy"))):
    m = session.get(ChapterDomainMapping, mapping_id)
    if m is None:
        raise HTTPException(status_code=404, detail="mapping not found")
    m.chapter_title = body.chapter_title
    m.domain_id = body.domain_id
    session.commit()
    return {"id": str(m.id)}


@router.delete("/mappings/{mapping_id}")
def delete_mapping(mapping_id: uuid.UUID, session: Session = Depends(get_session),
                   _: CurrentUser = Depends(require_permission("admin:manage_taxonomy"))):
    m = session.get(ChapterDomainMapping, mapping_id)
    if m is None:
        raise HTTPException(status_code=404, detail="mapping not found")
    session.delete(m)
    session.commit()
    return {"deleted": str(mapping_id)}
