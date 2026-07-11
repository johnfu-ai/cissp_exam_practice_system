"""Question bank HTTP API.

Routes delegate to ``app.services.question``. Mutations commit the session
after a successful service call; service exceptions map to HTTP statuses:
``NotFound`` -> 404, ``ValidationError`` -> 422, ``IllegalTransition`` -> 409.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.queries import not_deleted
from app.db.session import get_session
from app.dependencies import CurrentUser, require_permission
from app.models.question import Question, QuestionMapping, QuestionOption, QuestionTranslation
from app.schemas.question import (
    FeedbackIn,
    FeedbackOut,
    MappingsOut,
    OptionOut,
    QuestionCreateIn,
    QuestionListItem,
    QuestionOut,
    QuestionUpdateIn,
    ReviewAction,
    ReviewActionIn,
    RevisionOut,
    TranslationOut,
    TranslationOptionOut,
)
from app.services import question as svc

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _mappings_out(session: Session, question_id) -> dict:
    rows = session.execute(
        select(QuestionMapping).where(QuestionMapping.question_id == question_id)
    ).scalars().all()
    return {
        "domain_id": next((r.domain_id for r in rows if r.domain_id), None),
        "chapter_id": next((r.chapter_id for r in rows if r.chapter_id), None),
        "knowledge_point_id": next((r.knowledge_point_id for r in rows if r.knowledge_point_id), None),
        "tag_ids": [r.tag_id for r in rows if r.tag_id],
    }


def _question_out(session: Session, q) -> QuestionOut:
    options = sorted(
        session.execute(
            select(QuestionOption).where(QuestionOption.question_id == q.id)
        ).scalars().all(),
        key=lambda o: o.order_index,
    )
    translations = sorted(
        session.execute(
            select(QuestionTranslation).where(QuestionTranslation.question_id == q.id)
        ).scalars().all(),
        key=lambda t: t.language,
    )
    return QuestionOut(
        id=q.id,
        question_type=q.question_type,
        difficulty=q.difficulty,
        available_languages=list(q.available_languages or []),
        status=q.status,
        source=q.source,
        license_status=q.license_status,
        version=q.version,
        prompt_items=q.prompt_items,
        created_at=q.created_at,
        updated_at=q.updated_at,
        options=[
            OptionOut(id=o.id, order_index=o.order_index, is_correct=o.is_correct)
            for o in options
        ],
        translations=[
            TranslationOut(
                language=t.language,
                stem=t.stem,
                stem_format=t.stem_format,
                correct_answer_rationale=t.correct_answer_rationale,
                key_point_summary=t.key_point_summary,
                further_reading=t.further_reading,
                options=[TranslationOptionOut(**o) for o in t.options],
            )
            for t in translations
        ],
        mappings=MappingsOut(**_mappings_out(session, q.id)),
    )


def _feedback_out(fb) -> FeedbackOut:
    return FeedbackOut(
        id=fb.id, question_id=fb.question_id, reporter_id=fb.reporter_id,
        feedback_type=fb.feedback_type, comment=fb.comment, status=fb.status,
        created_at=fb.created_at,
    )


@router.get("", response_model=dict)
def list_questions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    question_type: str | None = None,
    difficulty: int | None = None,
    missing_language: str | None = None,
    search: str | None = None,
    domain_id: uuid.UUID | None = None,
    chapter_id: uuid.UUID | None = None,
    knowledge_point_id: uuid.UUID | None = None,
    tag_id: uuid.UUID | None = None,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:read")),
):
    from app.models.enums import QuestionStatus, QuestionType

    filters: dict = {}
    if status is not None:
        filters["status"] = QuestionStatus(status)
    if question_type is not None:
        filters["question_type"] = QuestionType(question_type)
    if difficulty is not None:
        filters["difficulty"] = difficulty
    if missing_language is not None:
        filters["missing_language"] = missing_language
    if search is not None:
        filters["search"] = search
    if domain_id is not None:
        filters["domain_id"] = domain_id
    if chapter_id is not None:
        filters["chapter_id"] = chapter_id
    if knowledge_point_id is not None:
        filters["knowledge_point_id"] = knowledge_point_id
    if tag_id is not None:
        filters["tag_id"] = tag_id
    items, total = svc.list_questions(
        session, org_id=current.org_id, page=page, size=size, filters=filters
    )
    # #13: batch the per-question domain lookup into ONE query (was one
    # select per question on the page -> N+1, 101 queries on a 100-item page).
    # Mirrors _mappings_out's "first non-null domain_id" semantics.
    page_qids = [q.id for q in items]
    domain_by_q: dict = {}
    if page_qids:
        for qid, did in session.execute(
            select(QuestionMapping.question_id, QuestionMapping.domain_id)
            .where(QuestionMapping.question_id.in_(page_qids))
            .order_by(QuestionMapping.question_id)
        ).all():
            if did is not None and qid not in domain_by_q:
                domain_by_q[qid] = did
    return {
        "items": [
            QuestionListItem(
                id=q.id,
                question_type=q.question_type,
                status=q.status,
                difficulty=q.difficulty,
                available_languages=list(q.available_languages or []),
                domain_id=domain_by_q.get(q.id),
                created_at=q.created_at,
            )
            for q in items
        ],
        "total": total, "page": page, "size": size,
    }


@router.post("", response_model=QuestionOut, status_code=200)
def create_question(
    body: QuestionCreateIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:write")),
):
    try:
        q = svc.create_question(
            session, org_id=current.org_id, actor_id=current.user.id, payload=body
        )
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(q)
    return _question_out(session, q)


@router.get("/language-coverage", response_model=dict)
def language_coverage(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("admin:view_reports")),
):
    """FR-LANG coverage report: count questions by en-only / zh-only / both / neither."""
    rows = session.execute(
        select(Question.available_languages).where(
            Question.organization_id == current.org_id, not_deleted(Question)
        )
    ).all()
    en_only = zh_only = both = neither = 0
    for (langs,) in rows:
        s = set(langs or [])
        if {"en", "zh"} <= s:
            both += 1
        elif "en" in s:
            en_only += 1
        elif "zh" in s:
            zh_only += 1
        else:
            neither += 1
    return {
        "en_only": en_only,
        "zh_only": zh_only,
        "both": both,
        "neither": neither,
        "total": en_only + zh_only + both + neither,
    }


@router.get("/{question_id}", response_model=QuestionOut)
def get_question(
    question_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:read")),
):
    try:
        q = svc.get_question(session, question_id, org_id=current.org_id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="question not found")
    return _question_out(session, q)


@router.put("/{question_id}", response_model=QuestionOut)
def update_question(
    question_id: uuid.UUID,
    body: QuestionUpdateIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:write")),
):
    try:
        q = svc.update_question(
            session, question_id=question_id, actor_id=current.user.id,
            payload=body, org_id=current.org_id,
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="question not found")
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(q)
    return _question_out(session, q)


@router.delete("/{question_id}")
def delete_question(
    question_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:write")),
):
    try:
        svc.delete_question(session, question_id=question_id,
                            actor_id=current.user.id, org_id=current.org_id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="question not found")
    session.commit()
    return {"deleted": str(question_id)}


@router.post("/{question_id}/review", response_model=QuestionOut)
def review_question(
    question_id: uuid.UUID,
    body: ReviewActionIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:write")),
):
    # approve/archive additionally require question:publish
    if body.action in (ReviewAction.approve, ReviewAction.archive) and \
            "question:publish" not in current.perms:
        raise HTTPException(status_code=403, detail="missing permission: question:publish")
    try:
        q = svc.submit_review(
            session, question_id=question_id, actor_id=current.user.id,
            action=body.action, comment=body.comment, org_id=current.org_id,
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="question not found")
    except svc.IllegalTransition as e:
        raise HTTPException(status_code=409, detail=str(e))
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    session.refresh(q)
    return _question_out(session, q)


@router.get("/{question_id}/revisions", response_model=list[RevisionOut])
def list_revisions(
    question_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:read")),
):
    try:
        svc.get_question(session, question_id, org_id=current.org_id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="question not found")
    return [
        RevisionOut(
            revision_number=r.revision_number, edited_by_id=r.edited_by_id,
            edited_at=r.created_at, change_summary=r.change_summary, snapshot=r.snapshot,
        )
        for r in svc.list_revisions(session, question_id)
    ]


@router.post("/{question_id}/feedback", response_model=FeedbackOut)
def create_feedback(
    question_id: uuid.UUID,
    body: FeedbackIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:read")),
):
    try:
        fb = svc.create_feedback(
            session, org_id=current.org_id, question_id=question_id,
            reporter_id=current.user.id, payload=body,
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="question not found")
    session.commit()
    session.refresh(fb)
    return _feedback_out(fb)


@router.get("/{question_id}/feedback", response_model=list[FeedbackOut])
def list_feedback(
    question_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("question:read")),
):
    try:
        svc.get_question(session, question_id, org_id=current.org_id)
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="question not found")
    return [_feedback_out(fb) for fb in svc.list_feedback(session, question_id=question_id)]
