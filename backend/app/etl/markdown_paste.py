"""Parse Markdown paste blocks into PRD §10.1-shaped row dicts (FR-IMP-02).

Grammar (blocks separated by blank lines or ``---``)::

    Stem text here?
    A. Option one
    B. Option two
    C. Option three
    D. Option four
    Answer: A
    Explanation: Why A is correct.

Chinese labels ``答案:`` / ``解析:`` are also accepted. Output rows are suitable
for ``JsonExtractor`` / ``_row_to_raw``.
"""

from __future__ import annotations

import hashlib
import re

_OPTION_RE = re.compile(r"^([A-Da-d])[\.\)]\s+(.*)$")
_ANSWER_RE = re.compile(r"^(?:Answer|答案)\s*[:：]\s*(.+)$", re.IGNORECASE)
_EXPLAIN_RE = re.compile(r"^(?:Explanation|解析)\s*[:：]\s*(.*)$", re.IGNORECASE)


def _split_blocks(markdown: str) -> list[str]:
    text = markdown.replace("\r\n", "\n").strip()
    if not text:
        return []
    # Split on --- or 2+ blank lines
    parts = re.split(r"\n---+\n|\n{2,}", text)
    return [p.strip() for p in parts if p.strip()]


def parse_markdown_paste(markdown: str) -> list[dict]:
    """Return a list of template row dicts (JSON-upload shape)."""
    rows: list[dict] = []
    for i, block in enumerate(_split_blocks(markdown), start=1):
        lines = [ln.rstrip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        stem_parts: list[str] = []
        options: dict[str, str] = {}
        answers: list[str] = []
        explanation = ""
        phase = "stem"
        for ln in lines:
            m_opt = _OPTION_RE.match(ln)
            m_ans = _ANSWER_RE.match(ln)
            m_exp = _EXPLAIN_RE.match(ln)
            if m_opt:
                phase = "options"
                options[m_opt.group(1).lower()] = m_opt.group(2).strip()
                continue
            if m_ans:
                phase = "meta"
                answers = [c.strip().upper() for c in re.split(r"[\s,;/]+", m_ans.group(1)) if c.strip()]
                continue
            if m_exp:
                phase = "meta"
                explanation = m_exp.group(1).strip()
                continue
            if phase == "stem":
                stem_parts.append(ln.strip())
            elif phase == "meta" and explanation:
                explanation = f"{explanation} {ln.strip()}".strip()
        stem = " ".join(stem_parts).strip()
        if not stem or len(options) < 2:
            continue
        qtype = "multiple_choice" if len(answers) > 1 else "single_choice"
        row: dict = {
            "question_text": stem,
            "question_type": qtype,
            "correct_answers": ",".join(answers) if answers else "",
            "explanation": explanation,
            "source": "markdown_paste",
        }
        for letter, text in sorted(options.items()):
            row[f"option_{letter}"] = text
        # Stable id helper for tests (JsonExtractor regenerates via _row_to_raw)
        row["_paste_index"] = i
        rows.append(row)
    return rows


def markdown_content_hash(markdown: str) -> str:
    return hashlib.sha1(markdown.encode("utf-8")).hexdigest()[:12]
