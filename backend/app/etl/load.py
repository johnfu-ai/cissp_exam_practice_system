"""ETL Load: one Question + N translations per external_id.

Owns all DB access and dedup by (dataset_slug, external_id) — language is NOT
part of the lookup (matches the unique constraint on QuestionExternalKey).
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
    Question,
    QuestionMapping,
    QuestionOption,
    QuestionRevision,
    QuestionTranslation,
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


def _existing_key(session, dataset_slug, external_id) -> QuestionExternalKey | None:
    """Dedup lookup — language is intentionally NOT part of the key."""
    return session.execute(
        select(QuestionExternalKey).filter_by(
            dataset_slug=dataset_slug, external_id=external_id
        )
    ).scalar_one_or_none()


def _translation_payload(cleaned, language):
    """Return (stem, rationale, [option_contents]) for one language.

    For zh, falls back to the en text when a field is empty so the translation
    row is never blank. A zh translation is only written when `has_zh`
    (i.e. zh is in cleaned.available_languages).
    """
    if language == "en":
        stem, rationale = cleaned.stem_en, cleaned.explanation_en
        opts = [(o.text_en if o.text_en else "") for o in cleaned.options]
    else:
        stem = cleaned.stem_zh if cleaned.stem_zh else cleaned.stem_en
        rationale = cleaned.explanation_zh if cleaned.explanation_zh else cleaned.explanation_en
        opts = [(o.text_zh if o.text_zh else o.text_en) for o in cleaned.options]
    return stem, rationale, opts


def _write_translations(session, q, cleaned):
    """Write one QuestionTranslation per language in cleaned.available_languages."""
    langs = list(cleaned.available_languages)
    for lang in langs:
        stem, rationale, opts = _translation_payload(cleaned, lang)
        session.add(QuestionTranslation(
            question_id=q.id,
            language=lang,
            stem=stem,
            stem_format=TextFormat.markdown,
            correct_answer_rationale=rationale,
            options=[
                {
                    "order_index": i,
                    "content": opts[i],
                    "content_format": "markdown",
                    "explanation": None,
                }
                for i in range(len(opts))
            ],
        ))
    q.available_languages = sorted(langs)


def _current_options(session, question_id) -> list[QuestionOption]:
    return list(
        session.execute(
            select(QuestionOption).filter_by(question_id=question_id).order_by(QuestionOption.order_index)
        ).scalars()
    )


def _current_translations(session, question_id) -> list[QuestionTranslation]:
    return list(
        session.execute(
            select(QuestionTranslation).where(QuestionTranslation.question_id == question_id)
        ).scalars().all()
    )


def _differs(q: Question, options: list[QuestionOption],
             translations: list[QuestionTranslation], cleaned) -> bool:
    """Compare the current question state to the cleaned record.

    Returns True on any of:
      - en translation missing or en stem changed,
      - canonical option correctness changed,
      - available_languages set changed (e.g. en-only -> en+zh supplementation),
      - zh translation stem changed, or zh missing on the question while cleaned
        carries zh (FR-LANG-08 supplementation path).

    Kept simple: a stem, answer-key, language-coverage, or zh-stem change counts
    as a diff.
    """
    t_en = next((t for t in translations if t.language == "en"), None)
    if t_en is None or t_en.stem != cleaned.stem_en:
        return True
    if [o.is_correct for o in options] != [o.is_correct for o in cleaned.options]:
        return True
    # available_languages change (e.g. en-only question gaining a zh translation)
    if sorted(q.available_languages or []) != sorted(cleaned.available_languages):
        return True
    # zh content change: supplementation (no zh row yet) or stem edit
    if "zh" in (cleaned.available_languages or []):
        t_zh = next((t for t in translations if t.language == "zh"), None)
        if t_zh is None or t_zh.stem != cleaned.stem_zh:
            return True
    return False


def _apply_one(session, resolvers, dataset_slug, import_job_id, cleaned) -> str:
    """Apply one cleaned record. Returns 'created' | 'updated' | 'unchanged'."""
    existing = _existing_key(session, dataset_slug, cleaned.external_id)
    status = QuestionStatus.needs_revision if cleaned.needs_revision else QuestionStatus.draft

    if existing is None:
        q = Question(
            organization_id=resolvers.org_id,
            question_type=cleaned.question_type,
            difficulty=cleaned.difficulty,
            status=status,
            source=cleaned.external_id,
            license_status=LicenseStatus.unconfirmed,
            import_job_id=import_job_id,
            prompt_items=cleaned.prompt_items,
            available_languages=sorted(cleaned.available_languages),
        )
        session.add(q)
        session.flush()
        # canonical options carry only order_index + is_correct (content is per-translation)
        for i, opt in enumerate(cleaned.options):
            session.add(QuestionOption(
                question_id=q.id, order_index=i, is_correct=opt.is_correct,
            ))
        _write_translations(session, q, cleaned)
        # one external key per external_id (language = first available, or None)
        first_lang = cleaned.available_languages[0] if cleaned.available_languages else None
        session.add(QuestionExternalKey(
            dataset_slug=dataset_slug, external_id=cleaned.external_id,
            language=first_lang, question_id=q.id,
        ))
        ch = resolvers.chapter(cleaned)
        session.add(QuestionMapping(
            question_id=q.id, chapter_id=ch.id, domain_id=resolvers.domain_id(cleaned),
        ))
        return "created"

    q = session.get(Question, existing.question_id)
    options = _current_options(session, q.id)
    translations = _current_translations(session, q.id)
    if not _differs(q, options, translations, cleaned):
        return "unchanged"

    # historical integrity: snapshot BEFORE update (translations included)
    old_snap = snapshot_question(q, translations, options)
    session.add(QuestionRevision(
        question_id=q.id, revision_number=q.version, snapshot=old_snap,
        change_summary="etl update",
    ))
    q.question_type = cleaned.question_type
    q.difficulty = cleaned.difficulty
    q.status = status
    q.prompt_items = cleaned.prompt_items
    q.version = (q.version or 1) + 1
    # replace canonical options
    for o in options:
        session.delete(o)
    session.flush()
    for i, opt in enumerate(cleaned.options):
        session.add(QuestionOption(
            question_id=q.id, order_index=i, is_correct=opt.is_correct,
        ))
    # replace translations
    for t in translations:
        session.delete(t)
    session.flush()
    _write_translations(session, q, cleaned)
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
                "language": None,
                "reason": f"{type(exc).__name__}: {exc}",
            })
    return result


def apply_dry_run(session, org_id, dataset_slug, cleaned_list) -> DryRunSummary:
    summary = DryRunSummary()
    for cleaned in cleaned_list:
        summary.by_type[cleaned.question_type.value] = (
            summary.by_type.get(cleaned.question_type.value, 0) + 1
        )
        # each cleaned record contributes one count per available language
        for lang in cleaned.available_languages:
            summary.by_language[lang] = summary.by_language.get(lang, 0) + 1
        existing = _existing_key(session, dataset_slug, cleaned.external_id)
        if existing is None:
            summary.would_create += 1
            continue
        q = session.get(Question, existing.question_id)
        options = _current_options(session, q.id)
        translations = _current_translations(session, q.id)
        if _differs(q, options, translations, cleaned):
            summary.would_update += 1
        else:
            summary.unchanged += 1
    return summary
