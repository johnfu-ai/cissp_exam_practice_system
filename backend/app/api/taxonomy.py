"""Taxonomy HTTP API (read + admin write)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dependencies import CurrentUser, require_permission
from app.models.taxonomy import ExamDomain
from app.schemas.taxonomy import (
    BindingIn,
    BlueprintIn,
    BlueprintOut,
    BlueprintUpdateIn,
    BookIn,
    BookOut,
    ChapterIn,
    ChapterOut,
    DomainIn,
    DomainOut,
    KnowledgePointIn,
    KnowledgePointOut,
    TagIn,
)
from app.services import taxonomy as svc
from app.services import taxonomy_admin as admin

router = APIRouter(prefix="/api", tags=["taxonomy"])


# --- Helpers ---


def _domain_out(d: ExamDomain) -> DomainOut:
    return DomainOut(
        id=d.id, blueprint_id=d.blueprint_id, number=d.number,
        name=d.name, weight_pct=d.weight_pct,
    )


def _blueprint_out(session: Session, bp) -> BlueprintOut:
    domains = [
        _domain_out(d) for d in session.execute(
            select(ExamDomain)
            .where(ExamDomain.blueprint_id == bp.id)
            .order_by(ExamDomain.number)
        ).scalars().all()
    ]
    return BlueprintOut(
        id=bp.id, version_label=bp.version_label, effective_date=bp.effective_date,
        min_items=bp.min_items, max_items=bp.max_items,
        duration_minutes=bp.duration_minutes, passing_score=bp.passing_score,
        max_score=bp.max_score, is_current=bp.is_current, domains=domains,
    )


# --- Read endpoints (question:read) ---


@router.get("/domains", response_model=list[DomainOut])
def domains(
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("question:read")),
):
    return [_domain_out(d) for d in svc.list_domains(session)]


@router.get("/books", response_model=list[BookOut])
def books(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:read")),
):
    return [
        BookOut(id=b.id, title=b.title, edition=b.edition, author=b.author,
                publisher=b.publisher)
        for b in svc.list_books(session, org_id=current.org_id)
    ]


@router.get("/books/{book_id}/chapters", response_model=list[ChapterOut])
def chapters(
    book_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:read")),
):
    chapters = svc.list_chapters(session, book_id=book_id, org_id=current.org_id)
    if chapters is None:
        raise HTTPException(status_code=404, detail="book not found")
    return [
        ChapterOut(id=c.id, book_id=c.book_id, order_index=c.order_index, title=c.title)
        for c in chapters
    ]


@router.get("/knowledge-points", response_model=list[KnowledgePointOut])
def knowledge_points(
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("question:read")),
):
    return [
        KnowledgePointOut(id=k.id, name=k.name, description=k.description,
                          parent_id=k.parent_id)
        for k in svc.list_knowledge_points(session)
    ]


# --- ExamBlueprint (admin:manage_taxonomy) ---


@router.post("/admin/blueprints", response_model=BlueprintOut)
def create_blueprint(
    body: BlueprintIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        bp = admin.create_blueprint(session, actor_id=current.user.id, payload=body)
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(bp)
    return _blueprint_out(session, bp)


@router.get("/admin/blueprints", response_model=list[BlueprintOut])
def list_blueprints(
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    return [_blueprint_out(session, bp) for bp in admin.list_blueprints(session)]


@router.get("/admin/blueprints/{blueprint_id}", response_model=BlueprintOut)
def get_blueprint(
    blueprint_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        bp = admin.get_blueprint(session, blueprint_id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="blueprint not found")
    return _blueprint_out(session, bp)


@router.put("/admin/blueprints/{blueprint_id}", response_model=BlueprintOut)
def update_blueprint(
    blueprint_id: uuid.UUID,
    body: BlueprintUpdateIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        bp = admin.update_blueprint(
            session, blueprint_id=blueprint_id, actor_id=current.user.id, payload=body
        )
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="blueprint not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(bp)
    return _blueprint_out(session, bp)


@router.post("/admin/blueprints/{blueprint_id}/set-current", response_model=BlueprintOut)
def set_current_blueprint(
    blueprint_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        bp = admin.set_current_blueprint(
            session, blueprint_id=blueprint_id, actor_id=current.user.id
        )
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="blueprint not found")
    session.commit()
    session.refresh(bp)
    return _blueprint_out(session, bp)


@router.delete("/admin/blueprints/{blueprint_id}")
def delete_blueprint(
    blueprint_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        admin.delete_blueprint(
            session, blueprint_id=blueprint_id, actor_id=current.user.id
        )
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="blueprint not found")
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return {"deleted": str(blueprint_id)}


# --- ExamDomain (admin:manage_taxonomy) ---


@router.post("/admin/blueprints/{blueprint_id}/domains", response_model=DomainOut)
def create_domain(
    blueprint_id: uuid.UUID,
    body: DomainIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        d = admin.create_domain(
            session, blueprint_id=blueprint_id, actor_id=current.user.id, payload=body
        )
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="blueprint not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    session.refresh(d)
    return _domain_out(d)


@router.get("/admin/blueprints/{blueprint_id}/domains", response_model=list[DomainOut])
def list_domains_for_blueprint(
    blueprint_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        domains = admin.list_domains_for_blueprint(session, blueprint_id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="blueprint not found")
    return [_domain_out(d) for d in domains]


@router.put(
    "/admin/blueprints/{blueprint_id}/domains/{domain_id}", response_model=DomainOut
)
def update_domain(
    blueprint_id: uuid.UUID,
    domain_id: uuid.UUID,
    body: DomainIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        d = admin.update_domain(
            session, blueprint_id=blueprint_id, domain_id=domain_id,
            actor_id=current.user.id, payload=body,
        )
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="domain not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    session.refresh(d)
    return _domain_out(d)


@router.delete("/admin/blueprints/{blueprint_id}/domains/{domain_id}")
def delete_domain(
    blueprint_id: uuid.UUID,
    domain_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        admin.delete_domain(
            session, blueprint_id=blueprint_id, domain_id=domain_id,
            actor_id=current.user.id,
        )
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="domain not found")
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return {"deleted": str(domain_id)}


# --- Book (tenant-scoped) ---


@router.post("/books", response_model=BookOut)
def create_book(
    body: BookIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        book = admin.create_book(
            session, org_id=current.org_id, actor_id=current.user.id, payload=body
        )
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(book)
    return BookOut(id=book.id, title=book.title, edition=book.edition,
                   author=book.author, publisher=book.publisher)


@router.get("/books/{book_id}", response_model=BookOut)
def get_book(
    book_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:read")),
):
    try:
        book = admin.get_book(session, book_id=book_id, org_id=current.org_id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="book not found")
    return BookOut(id=book.id, title=book.title, edition=book.edition,
                   author=book.author, publisher=book.publisher)


@router.put("/books/{book_id}", response_model=BookOut)
def update_book(
    book_id: uuid.UUID,
    body: BookIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        book = admin.update_book(
            session, book_id=book_id, org_id=current.org_id,
            actor_id=current.user.id, payload=body,
        )
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="book not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(book)
    return BookOut(id=book.id, title=book.title, edition=book.edition,
                   author=book.author, publisher=book.publisher)


@router.delete("/books/{book_id}")
def delete_book(
    book_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        admin.delete_book(
            session, book_id=book_id, org_id=current.org_id,
            actor_id=current.user.id,
        )
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="book not found")
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return {"deleted": str(book_id)}


# --- Chapter (tenant-scoped, nested under book) ---


@router.post("/books/{book_id}/chapters", response_model=ChapterOut)
def create_chapter(
    book_id: uuid.UUID,
    body: ChapterIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        ch = admin.create_chapter(
            session, book_id=book_id, org_id=current.org_id,
            actor_id=current.user.id, payload=body,
        )
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="book not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(ch)
    return ChapterOut(id=ch.id, book_id=ch.book_id, order_index=ch.order_index,
                      title=ch.title)


@router.put("/books/{book_id}/chapters/{chapter_id}", response_model=ChapterOut)
def update_chapter(
    book_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: ChapterIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        ch = admin.update_chapter(
            session, book_id=book_id, chapter_id=chapter_id, org_id=current.org_id,
            actor_id=current.user.id, payload=body,
        )
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="chapter not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(ch)
    return ChapterOut(id=ch.id, book_id=ch.book_id, order_index=ch.order_index,
                      title=ch.title)


@router.delete("/books/{book_id}/chapters/{chapter_id}")
def delete_chapter(
    book_id: uuid.UUID,
    chapter_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        admin.delete_chapter(
            session, book_id=book_id, chapter_id=chapter_id, org_id=current.org_id,
            actor_id=current.user.id,
        )
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="chapter not found")
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return {"deleted": str(chapter_id)}


# --- KnowledgePoint (tree, GLOBAL) ---


@router.post("/knowledge-points", response_model=KnowledgePointOut)
def create_knowledge_point(
    body: KnowledgePointIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        kp = admin.create_knowledge_point(
            session, actor_id=current.user.id, payload=body
        )
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="parent knowledge point not found")
    session.commit()
    session.refresh(kp)
    return KnowledgePointOut(id=kp.id, name=kp.name, description=kp.description,
                             parent_id=kp.parent_id)


@router.get("/knowledge-points/{kp_id}", response_model=KnowledgePointOut)
def get_knowledge_point(
    kp_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("question:read")),
):
    try:
        kp = admin.get_knowledge_point(session, kp_id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="knowledge point not found")
    return KnowledgePointOut(id=kp.id, name=kp.name, description=kp.description,
                             parent_id=kp.parent_id)


@router.put("/knowledge-points/{kp_id}", response_model=KnowledgePointOut)
def update_knowledge_point(
    kp_id: uuid.UUID,
    body: KnowledgePointIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        kp = admin.update_knowledge_point(
            session, kp_id=kp_id, actor_id=current.user.id, payload=body
        )
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="knowledge point not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(kp)
    return KnowledgePointOut(id=kp.id, name=kp.name, description=kp.description,
                             parent_id=kp.parent_id)


@router.delete("/knowledge-points/{kp_id}")
def delete_knowledge_point(
    kp_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        admin.delete_knowledge_point(session, kp_id=kp_id, actor_id=current.user.id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="knowledge point not found")
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return {"deleted": str(kp_id)}


# --- KnowledgePoint <-> Domain binding (admin) ---


@router.post(
    "/admin/knowledge-points/{kp_id}/domains", response_model=DomainOut
)
def bind_kp_domain(
    kp_id: uuid.UUID,
    body: BindingIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        binding = admin.bind_kp_domain(
            session, kp_id=kp_id, actor_id=current.user.id, payload=body
        )
        session.refresh(binding)
        d = session.get(ExamDomain, binding.domain_id)
    except admin.NotFound:
        raise HTTPException(
            status_code=404, detail="knowledge point or domain not found"
        )
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return _domain_out(d)


@router.get(
    "/admin/knowledge-points/{kp_id}/domains", response_model=list[DomainOut]
)
def list_kp_domains(
    kp_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        domains = admin.list_kp_domains(session, kp_id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="knowledge point not found")
    return [_domain_out(d) for d in domains]


@router.delete("/admin/knowledge-points/{kp_id}/domains/{domain_id}")
def unbind_kp_domain(
    kp_id: uuid.UUID,
    domain_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        admin.unbind_kp_domain(
            session, kp_id=kp_id, domain_id=domain_id, actor_id=current.user.id
        )
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="binding not found")
    session.commit()
    return {"deleted": str(domain_id)}


# --- Tag (GLOBAL) ---


@router.post("/tags")
def create_tag(
    body: TagIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        tag = admin.create_tag(session, actor_id=current.user.id, payload=body)
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    session.refresh(tag)
    return {"id": tag.id, "name": tag.name, "description": tag.description}


@router.get("/tags")
def list_tags(
    session: Session = Depends(get_session),
    _: CurrentUser = Depends(require_permission("question:read")),
):
    return [
        {"id": t.id, "name": t.name, "description": t.description}
        for t in admin.list_tags(session)
    ]


@router.put("/tags/{tag_id}")
def update_tag(
    tag_id: uuid.UUID,
    body: TagIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        tag = admin.update_tag(
            session, tag_id=tag_id, actor_id=current.user.id, payload=body
        )
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="tag not found")
    except admin.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    session.refresh(tag)
    return {"id": tag.id, "name": tag.name, "description": tag.description}


@router.delete("/tags/{tag_id}")
def delete_tag(
    tag_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:manage_taxonomy")),
):
    try:
        admin.delete_tag(session, tag_id=tag_id, actor_id=current.user.id)
    except admin.NotFound:
        raise HTTPException(status_code=404, detail="tag not found")
    except admin.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.commit()
    return {"deleted": str(tag_id)}
