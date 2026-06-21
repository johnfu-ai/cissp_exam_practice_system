"""ETL Load: apply CleanedQuestion create-or-update within one transaction.

Owns all DB access and dedup by (dataset_slug, external_id, language).
Savepoint-per-record for error isolation. Caller controls commit.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import LicenseStatus, QuestionStatus, TextFormat
from app.models.etl import ChapterDomainMapping, QuestionExternalKey
from app.models.question import (
    Book,
    Chapter,
    Explanation,
    Question,
    QuestionMapping,
    QuestionOption,
    QuestionRevision,
)
from app.services.snapshot import snapshot_question


@dataclass
class LoadResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    errors: list[dict] = field(default_factory=list)


@dataclass
class DryRunSummary:
    would_create: int = 0
    would_update: int = 0
    unchanged: int = 0
    errors: list[dict] = field(default_factory=list)
    by_type: dict = field(default_factory=dict)
    by_language: dict = field(default_factory=dict)


class _Resolvers:
    """Caches Book/Chapter/Domain lookups for a batch."""

    def __init__(self, session: Session, org_id: uuid.UUID, dataset_slug: str):
        self.session = session
        self.org_id = org_id
        self.dataset_slug = dataset_slug
        self._books: dict[tuple[str, str], Book] = {}
        self._chapters: dict[tuple[uuid.UUID, int], Chapter] = {}
        self._domains: dict[int, uuid.UUID | None] = {}

    def book(self, cleaned) -> Book:
        key = ("CISSP OSG", "10")
        if key not in self._books:
            book = self.session.execute(
                select(Book).filter_by(title="CISSP OSG", edition="10", organization_id=self.org_id)
            ).scalar_one_or_none()
            if book is None:
                book = Book(title="CISSP OSG", edition="10", organization_id=self.org_id)
                self.session.add(book)
                self.session.flush()
            self._books[key] = book
        return self._books[key]

    def chapter(self, cleaned) -> Chapter:
        book = self.book(cleaned)
        key = (book.id, cleaned.source_chapter)
        if key not in self._chapters:
            ch = self.session.execute(
                select(Chapter).filter_by(book_id=book.id, order_index=cleaned.source_chapter)
            ).scalar_one_or_none()
            if ch is None:
                ch = Chapter(
                    book_id=book.id,
                    order_index=cleaned.source_chapter,
                    title=cleaned.source_chapter_title,
                    organization_id=self.org_id,
                )
                self.session.add(ch)
                self.session.flush()
            self._chapters[key] = ch
        return self._chapters[key]

    def domain_id(self, cleaned) -> uuid.UUID | None:
        if cleaned.source_chapter not in self._domains:
            cdm = self.session.execute(
                select(ChapterDomainMapping).filter_by(
                    dataset_slug=self.dataset_slug, chapter_number=cleaned.source_chapter
                )
            ).scalar_one_or_none()
            self._domains[cleaned.source_chapter] = cdm.domain_id if cdm else None
        return self._domains[cleaned.source_chapter]


def _existing_key(session, dataset_slug, external_id, language) -> QuestionExternalKey | None:
    return session.execute(
        select(QuestionExternalKey).filter_by(
            dataset_slug=dataset_slug, external_id=external_id, language=language
        )
    ).scalar_one_or_none()


def _current_options(session, question_id) -> list[QuestionOption]:
    return list(
        session.execute(
            select(QuestionOption).filter_by(question_id=question_id).order_by(QuestionOption.order_index)
        ).scalars()
    )


def _differs(q: Question, options: list[QuestionOption], cleaned) -> bool:
    if q.stem != cleaned.stem:
        return True
    if q.question_type != cleaned.question_type:
        return True
    if [o.content for o in options] != [o.content for o in cleaned.options]:
        return True
    if [o.is_correct for o in options] != [o.is_correct for o in cleaned.options]:
        return True
    return False


def _apply_one(session, resolvers, dataset_slug, import_job_id, cleaned) -> str:
    """Apply one cleaned record. Returns 'created'|'updated'|'unchanged'."""
    existing = _existing_key(session, dataset_slug, cleaned.external_id, cleaned.language)
    status = QuestionStatus.needs_revision if cleaned.needs_revision else QuestionStatus.draft

    if existing is None:
        q = Question(
            organization_id=resolvers.org_id,
            question_type=cleaned.question_type,
            stem=cleaned.stem,
            stem_format=TextFormat.markdown,
            difficulty=cleaned.difficulty,
            language=cleaned.language,
            status=status,
            source=cleaned.external_id,
            license_status=LicenseStatus.unconfirmed,
            import_job_id=import_job_id,
            prompt_items=cleaned.prompt_items,
        )
        session.add(q)
        session.flush()
        for i, opt in enumerate(cleaned.options):
            session.add(QuestionOption(
                question_id=q.id, order_index=i, content=opt.content,
                content_format=TextFormat.markdown, is_correct=opt.is_correct,
            ))
        session.add(Explanation(
            question_id=q.id, correct_answer_rationale=cleaned.explanation,
        ))
        session.add(QuestionExternalKey(
            dataset_slug=dataset_slug, external_id=cleaned.external_id,
            language=cleaned.language, question_id=q.id,
        ))
        ch = resolvers.chapter(cleaned)
        session.add(QuestionMapping(
            question_id=q.id, chapter_id=ch.id, domain_id=resolvers.domain_id(cleaned),
        ))
        return "created"

    q = session.get(Question, existing.question_id)
    options = _current_options(session, q.id)
    if not _differs(q, options, cleaned):
        return "unchanged"

    # historical integrity: snapshot BEFORE update
    old_snap = snapshot_question(q, options)
    session.add(QuestionRevision(
        question_id=q.id, revision_number=q.version, snapshot=old_snap,
        change_summary="etl update",
    ))
    q.stem = cleaned.stem
    q.question_type = cleaned.question_type
    q.difficulty = cleaned.difficulty
    q.status = status
    q.prompt_items = cleaned.prompt_items
    q.version = (q.version or 1) + 1
    # replace options
    for o in options:
        session.delete(o)
    session.flush()
    for i, opt in enumerate(cleaned.options):
        session.add(QuestionOption(
            question_id=q.id, order_index=i, content=opt.content,
            content_format=TextFormat.markdown, is_correct=opt.is_correct,
        ))
    # update explanation
    expl = session.execute(select(Explanation).filter_by(question_id=q.id)).scalar_one_or_none()
    if expl is None:
        session.add(Explanation(question_id=q.id, correct_answer_rationale=cleaned.explanation))
    else:
        expl.correct_answer_rationale = cleaned.explanation
    return "updated"


def apply_load(session, org_id, dataset_slug, import_job_id, cleaned_list) -> LoadResult:
    resolvers = _Resolvers(session, org_id, dataset_slug)
    result = LoadResult()
    for cleaned in cleaned_list:
        try:
            sp = session.begin_nested()
            outcome = _apply_one(session, resolvers, dataset_slug, import_job_id, cleaned)
            sp.commit()
            if outcome == "created":
                result.created += 1
            elif outcome == "updated":
                result.updated += 1
            else:
                result.unchanged += 1
        except Exception as exc:
            # Roll back ONLY this record's savepoint — a bare session.rollback()
            # would undo the outer transaction and lose prior records' commits.
            try:
                sp.rollback()
            except Exception:
                pass
            result.errors.append({
                "external_id": cleaned.external_id,
                "language": cleaned.language,
                "reason": f"{type(exc).__name__}: {exc}",
            })
    return result


def apply_dry_run(session, org_id, dataset_slug, cleaned_list) -> DryRunSummary:
    summary = DryRunSummary()
    for cleaned in cleaned_list:
        summary.by_type[cleaned.question_type.value] = summary.by_type.get(cleaned.question_type.value, 0) + 1
        summary.by_language[cleaned.language] = summary.by_language.get(cleaned.language, 0) + 1
        existing = _existing_key(session, dataset_slug, cleaned.external_id, cleaned.language)
        if existing is None:
            summary.would_create += 1
            continue
        q = session.get(Question, existing.question_id)
        options = _current_options(session, q.id)
        summary.would_update += 1 if _differs(q, options, cleaned) else 0
        summary.unchanged += 0 if _differs(q, options, cleaned) else 1
    return summary
