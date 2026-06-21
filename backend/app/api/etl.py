"""ETL HTTP API. Unauthenticated stubs until auth/JWT sub-project lands.
Each handler carries # TODO(auth): replace with real org/user from JWT.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.etl.runner import run_commit, run_preview, run_rollback
from app.models.auth import Organization
from app.models.etl import ChapterDomainMapping, EtlDataset, EtlRun

router = APIRouter(prefix="/api/etl", tags=["etl"])


def _org_id(session: Session) -> uuid.UUID:
    # TODO(auth): replace with real org from JWT.
    org = session.execute(select(Organization).limit(1)).scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=500, detail="no organization seeded")
    return org.id


class CreateRunIn(BaseModel):
    dataset_slug: str


class MappingIn(BaseModel):
    dataset_slug: str
    chapter_number: int
    chapter_title: str
    domain_id: uuid.UUID | None = None


@router.get("/datasets")
def list_datasets(session: Session = Depends(get_session)):
    rows = session.execute(select(EtlDataset)).scalars().all()
    return [
        {
            "id": str(d.id), "slug": d.slug, "name": d.name,
            "source_path": d.source_path, "total_questions": d.total_questions,
            "languages": d.languages,
        }
        for d in rows
    ]


@router.get("/datasets/{slug}")
def get_dataset(slug: str, session: Session = Depends(get_session)):
    d = session.execute(select(EtlDataset).filter_by(slug=slug)).scalar_one_or_none()
    if d is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return {"id": str(d.id), "slug": d.slug, "name": d.name,
            "source_path": d.source_path, "total_questions": d.total_questions,
            "languages": d.languages}


@router.post("/runs")
def create_run(body: CreateRunIn, session: Session = Depends(get_session)):
    # TODO(auth): initiated_by_id from JWT.
    org_id = _org_id(session)
    ds = session.execute(select(EtlDataset).filter_by(slug=body.dataset_slug)).scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    run = run_preview(session, org_id, ds)
    session.commit()
    return {"run_id": str(run.id), "phase": run.phase.value, "preview_summary": run.preview_summary}


@router.get("/runs/{run_id}")
def get_run(run_id: uuid.UUID, session: Session = Depends(get_session)):
    run = session.get(EtlRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": str(run.id), "phase": run.phase.value,
            "preview_summary": run.preview_summary, "committed_at": run.committed_at}


@router.post("/runs/{run_id}/commit")
def commit_run(run_id: uuid.UUID, session: Session = Depends(get_session)):
    # TODO(auth): org_id from JWT.
    org_id = _org_id(session)
    try:
        run = run_commit(session, org_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    session.commit()
    return {"run_id": str(run.id), "phase": run.phase.value}


@router.post("/runs/{run_id}/rollback")
def rollback_run(run_id: uuid.UUID, session: Session = Depends(get_session)):
    try:
        run = run_rollback(session, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    session.commit()
    return {"run_id": str(run.id), "phase": run.phase.value}


@router.get("/mappings")
def list_mappings(dataset_slug: str | None = None, session: Session = Depends(get_session)):
    stmt = select(ChapterDomainMapping)
    if dataset_slug:
        stmt = stmt.filter_by(dataset_slug=dataset_slug)
    rows = session.execute(stmt).scalars().all()
    return [
        {"id": str(m.id), "dataset_slug": m.dataset_slug,
         "chapter_number": m.chapter_number, "chapter_title": m.chapter_title,
         "domain_id": str(m.domain_id) if m.domain_id else None}
        for m in rows
    ]


@router.post("/mappings")
def create_mapping(body: MappingIn, session: Session = Depends(get_session)):
    m = ChapterDomainMapping(
        dataset_slug=body.dataset_slug, chapter_number=body.chapter_number,
        chapter_title=body.chapter_title, domain_id=body.domain_id,
    )
    session.add(m)
    session.commit()
    return {"id": str(m.id), "dataset_slug": m.dataset_slug,
            "chapter_number": m.chapter_number}


@router.put("/mappings/{mapping_id}")
def update_mapping(mapping_id: uuid.UUID, body: MappingIn, session: Session = Depends(get_session)):
    m = session.get(ChapterDomainMapping, mapping_id)
    if m is None:
        raise HTTPException(status_code=404, detail="mapping not found")
    m.chapter_title = body.chapter_title
    m.domain_id = body.domain_id
    session.commit()
    return {"id": str(m.id)}


@router.delete("/mappings/{mapping_id}")
def delete_mapping(mapping_id: uuid.UUID, session: Session = Depends(get_session)):
    m = session.get(ChapterDomainMapping, mapping_id)
    if m is None:
        raise HTTPException(status_code=404, detail="mapping not found")
    session.delete(m)
    session.commit()
    return {"deleted": str(mapping_id)}
