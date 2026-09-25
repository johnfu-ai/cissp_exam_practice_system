"""Exam paper-export converter (FR-ETL-17).

Reads raw exam paper exports (``paper_*.json`` documents exported from a
paper platform) and emits a standard ETL dataset directory
(``manifest.json`` + ``questions.jsonl`` + ``papers.json``, §10.3 PRD v1.4).

The module is pure (no DB, no source mutation) so it can be unit-tested and
run idempotently:

    python -m app.etl.paper_export <exports_dir> <out_dir>
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

BOOK_NAME = "CISSP 模拟试卷"
EDITION = 1
_DATASET_SLUG = "mockpapers"

# CJK ideographs + CJK punctuation + fullwidth forms — the boundary of a
# Chinese segment inside otherwise-Latin source text.
_CJK_RE = re.compile(r"[　-〿一-鿿＀-￯]")
_P_BLOCK_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
_SPAN_RE = re.compile(r"</?span[^>]*>")
_TAG_ATTR_P_RE = re.compile(r"<p[^>]*>")
_OPTION_LETTER_RE = re.compile(r"^\s*[A-Za-z]\s*[.、．:：]\s*")

_CN_NUMERAL = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def normalize_rich_text(text: str) -> str:
    """Normalize Word-export residue while keeping safe structure.

    - ``&nbsp;`` → space
    - strip ``class``/``style``-carrying wrappers: ``<p class="MsoNormal">`` → ``<p>``,
      ``<span style="...">…</span>`` → inner content (``<img>`` tags survive)
    """
    if not text:
        return ""
    out = text.replace("\r\n", "\n").replace("&nbsp;", " ")
    out = _SPAN_RE.sub("", out)
    out = _TAG_ATTR_P_RE.sub("<p>", out)
    return out.strip()


def _strip_p_wrappers(text: str) -> str:
    out = re.sub(r"^\s*<p>", "", text)
    out = re.sub(r"</p>\s*$", "", out)
    return out.strip()


def _blocks(text: str) -> list[str] | None:
    matches = _P_BLOCK_RE.findall(text)
    if matches:
        return [m.strip() for m in matches if m.strip()]
    return None


def split_bilingual(text: str) -> tuple[str, str]:
    """Split an export text into ``(en, zh)``.

    Prefers ``<p>``-block granularity (English blocks vs CJK blocks); falls
    back to the first CJK-character boundary for inline-mixed text.
    """
    normalized = normalize_rich_text(text)
    if not normalized:
        return "", ""

    blk = _blocks(normalized)
    if blk:
        # boundary-split every block, then join per language — handles
        # English blocks, Chinese blocks, and single mixed blocks alike.
        en_parts: list[str] = []
        zh_parts: list[str] = []
        for block in blk:
            b_en, b_zh = _split_inline(block)
            if b_en:
                en_parts.append(b_en)
            if b_zh:
                zh_parts.append(b_zh)
        return "\n\n".join(en_parts).strip(), "\n\n".join(zh_parts).strip()

    return _split_inline(normalized)


def _split_inline(text: str) -> tuple[str, str]:
    m = _CJK_RE.search(text)
    if not m:
        return text.strip(), ""
    idx = m.start()
    if idx == 0:
        return "", text.strip()
    return text[:idx].rstrip(), text[idx:].lstrip()


def strip_option_letter(text: str) -> str:
    """Remove the leading ``A.`` / ``B、`` letter prefix from an option."""
    normalized = normalize_rich_text(text)
    unwrapped = _strip_p_wrappers(normalized)
    return _OPTION_LETTER_RE.sub("", unwrapped, count=1).strip()


def _paper_domain_number(paper_name: str) -> int | None:
    for char, number in _CN_NUMERAL.items():
        if re.search(rf"{char}[.．、]", paper_name):
            return number
    return None


def _option_analysis(raw_option: dict[str, Any]) -> str:
    return normalize_rich_text(raw_option.get("answerAnalysis") or "")


def convert_question(
    raw_question: dict[str, Any],
    *,
    chapter: int,
    chapter_title: str,
    domain_number: int | None,
    paper_external_id: str,
) -> dict[str, Any] | None:
    """Convert one export question record to the standard dataset shape."""
    qid = raw_question.get("id") or raw_question.get("paperQuestionId")
    if not qid:
        return None

    options_raw = raw_question.get("questionAnswers") or []
    options: list[dict[str, Any]] = []
    correct_keys: list[str] = []
    option_explanations: dict[str, dict[str, str]] = {}
    for index, raw_option in enumerate(options_raw):
        key = chr(ord("A") + index)
        content = strip_option_letter(raw_option.get("answerContent") or "")
        en, zh = split_bilingual(content)
        options.append({"key": key, "text": {"en": en, "zh": zh}})
        if raw_option.get("isCorrect"):
            correct_keys.append(key)
        analysis = _option_analysis(raw_option)
        if analysis:
            a_en, a_zh = split_bilingual(analysis)
            option_explanations[key] = {"en": a_en, "zh": a_zh}

    if len(correct_keys) > 1:
        q_type = "multiple_choice"
    else:
        q_type = "single_choice"

    # Question-level explanation prefers the correct option's analysis,
    # falling back to the first non-empty option analysis.
    explanation_en = explanation_zh = ""
    analysis_source = next(
        (options_raw[i] for i, k in enumerate(
            [chr(ord("A") + i) for i in range(len(options_raw))])
         if k in correct_keys and _option_analysis(options_raw[i])),
        None,
    )
    if analysis_source is None:
        analysis_source = next(
            (o for o in options_raw if _option_analysis(o)), None)
    if analysis_source is not None:
        explanation_en, explanation_zh = split_bilingual(
            _option_analysis(analysis_source))

    stem_en, stem_zh = split_bilingual(
        raw_question.get("questionName") or "")

    return {
        "id": f"paper-{qid}",
        "source": {
            "book": BOOK_NAME,
            "edition": EDITION,
            "section": "exam",
            "chapter": chapter,
            "chapter_title": chapter_title,
            "number": raw_question.get("sort") or 0,
            "domain_number": domain_number,
        },
        "type": q_type,
        "stem": {"en": stem_en, "zh": stem_zh},
        "options": options,
        "correct_keys": correct_keys,
        "explanation": {"en": explanation_en, "zh": explanation_zh},
        "option_explanations": option_explanations or None,
        "license_status": "unconfirmed",
        "meta": {
            "export": {
                "question_id": str(qid),
                "paper_id": str(paper_external_id),
            },
        },
    }


def convert_paper(document: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Convert one ``paper_*.json`` document to ``(paper_row, question_records)``."""
    paper_meta = document["paper"]
    paper_external_id = str(paper_meta["id"])
    paper_name = paper_meta["paperName"]
    domain_number = _paper_domain_number(paper_name)

    questions = sorted(
        document.get("questions") or [], key=lambda q: q.get("sort") or 0)
    records: list[dict[str, Any]] = []
    question_ids: list[str] = []
    scores: list[Any] = []
    for raw_question in questions:
        record = convert_question(
            raw_question,
            chapter=domain_number or 0,
            chapter_title=paper_name,
            domain_number=domain_number,
            paper_external_id=paper_external_id,
        )
        if record is None:
            continue
        records.append(record)
        question_ids.append(record["id"])
        scores.append(raw_question.get("score") or 1)

    total_score = paper_meta.get("totalScore")
    if total_score is None:
        total_score = sum(scores)

    paper_row = {
        "id": paper_external_id,
        "name": paper_name,
        "description": f"{BOOK_NAME}",
        "duration_minutes": paper_meta.get("examDuration"),
        "domain_number": domain_number,
        "question_ids": question_ids,
        "scores": scores,
        "total_score": total_score,
        "status": "published",
    }
    return paper_row, records


def convert_exports(exports_dir: Path | str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert every ``paper_*.json`` under ``exports_dir``.

    Returns ``(manifest, question_records, paper_rows)``; pure function.
    """
    exports_path = Path(exports_dir)
    files = sorted(exports_path.glob("paper_*.json"))
    if not files:
        raise FileNotFoundError(f"no paper_*.json exports under {exports_path}")

    records_by_id: dict[str, dict[str, Any]] = {}
    paper_rows: list[dict[str, Any]] = []
    for file in files:
        document = json.loads(file.read_text(encoding="utf-8"))
        paper_row, records = convert_paper(document)
        paper_rows.append(paper_row)
        for record in records:
            records_by_id.setdefault(record["id"], record)

    records = [records_by_id[k] for k in sorted(records_by_id)]
    type_counts: dict[str, int] = {}
    for record in records:
        type_counts[record["type"]] = type_counts.get(record["type"], 0) + 1

    manifest = {
        "source": f"paper exam exports ({len(files)} papers, {_DATASET_SLUG})",
        "dataset_slug": _DATASET_SLUG,
        "total_questions": len(records),
        "chapters": len(paper_rows),
        "type_counts": type_counts,
        "papers_count": len(paper_rows),
        "has_papers": True,
    }
    return manifest, records, paper_rows


def write_dataset(
    out_dir: Path | str,
    manifest: dict[str, Any],
    records: list[dict[str, Any]],
    papers: list[dict[str, Any]],
) -> None:
    """Write the standard dataset layout (§10.3)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (out / "questions.jsonl").open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    (out / "papers.json").write_text(
        json.dumps({"papers": papers}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert paper exports to an ETL dataset")
    parser.add_argument("exports_dir", help="directory containing paper_*.json exports")
    parser.add_argument("out_dir", help="output dataset directory")
    args = parser.parse_args(argv)

    manifest, records, papers = convert_exports(args.exports_dir)
    write_dataset(args.out_dir, manifest, records, papers)
    print(
        f"wrote {len(records)} questions / {len(papers)} papers "
        f"to {args.out_dir} (types: {manifest['type_counts']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
